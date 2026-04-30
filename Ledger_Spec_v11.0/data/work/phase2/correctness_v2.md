# Phase 2 — Cross-Layer Correctness Synthesis (Correctness-Architect Stance, **v2**)

**Author role.** Correctness Architect — end-to-end consistency across the
data layer, the unit store, the executor, the valuation FSM, the settlement
projection, and the obligation/liveness machinery.

**Revision provenance.** This file (`correctness_v2.md`) is the Round-2 revision
in response to Round-1 adversarial findings consolidated in
`/home/renaud/A61E33BB10/Ledger_Spec_v11.0/data/work/phase3/round1/R1_consolidated_findings.md`
and the in-role independent review at
`/home/renaud/A61E33BB10/Ledger_Spec_v11.0/data/work/phase3/round1/correctness.md`.

**Posture for v2.** I do not retreat from any v1 claim that survived review;
I do **promote conditional assumptions to structural invariants** where
closure-under-composition fails, **expand the boundary catalogue from 12 to
17** with explicit structural-unreachability justification for any number
lower, **expand the Goodhart trap list from 4 to 5** with concrete detection
mechanisms, **specify a fault-injection harness** for every previously-named
fault row, and **add five mutation operators** plus per-stratum coverage
targets and witness-type runtime checkers to close the Goodhart traps that
v1 named but did not actually trap.

---

## §0 — Changes from v1

This section enumerates every substantive change from `correctness.md` (v1).
Each change is keyed to the Round-1 finding(s) that motivated it.

### §0.1 — Laws strengthened (L1–L14, plus a new bridging law)

| Change | v1 statement | v2 statement | R1 finding |
|---|---|---|---|
| **L1** | Witness = recursive lineage walk; retention horizon a conditional assumption | **Structural invariant**: every snapshot referenced by a non-terminal `ValuationRecord` MUST be retained until that record reaches a terminal lifecycle state. Pre-commit lineage walk is a **gating predicate** for FSM `Stale → Pricing` re-entry (not just a post-hoc test). | A.1, T7, T10 |
| **L4** | Bitemporal coherence under finite knowledge histories | Add **bounded vendor-restatement chain length** ($\kappa_{\text{restate}}$) and **bounded clock-skew interleaving** witness. Reclassify from "unwitnessed" to "**witnessed-by-induction**": replay is total by structural induction over the restatement chain when retention horizon $\ge \tau_{\text{tenor}}$. | T7, D.4 |
| **L5/L6/L7** | Per-event-class / per-mandate / per-CCP conservation only | Add **L15 Novation Bridge Conservation**: for `BusinessEvent ∈ Novation_Set` (single-CCP and multi-CCP), conservation holds in the **union scope** during the bridge transaction; the law is satisfied either by union-scope ∑Δ = 0 or by an explicit two-tx decomposition with a registered bridge `Obligation`. Per-component conservation may legally fail per-leg of the bridge tx. | A.2 |
| **L6** | Mandate-as-unit conservation | Strengthen oracle: HWM lives **only** at `PositionState[w, u_MA]` *and* the firm's `fee_reserve` virtual wallet is structurally typed `FeeReserve` (not a free `Wallet`) so `M-CONS` cannot accidentally "pass" by routing fees into a non-conservation field. | C.5 (witness laundering) |
| **L8** | Replay determinism under modelled non-determinism | Strengthen oracle: replay tested under (a) **two storage engines** (B14), (b) **adversarial activity-completion order** (B15), (c) **bit-identical pricer outputs** under pinned BLAS/threads (B13). Reclassify cosmic-ray surrogate as **witnessable with bound ε** computed from erasure-coding parameters $(n,k)$. | B.1–B.3 |
| **L9** | Forgetful composition for referentially-independent events | Strengthen oracle: explicit **dependence-relation lattice** $\mathcal{D} = (\text{trade-lineage}, \text{timestamp-order}, \text{snapshot-shared}, \text{capability-shared})$; partition events by which $\mathcal{D}$-relation they share, then assert composition law per partition. | E.2 |
| **L10** | Workflow-history replay coherence | Strengthen oracle: `tx_id = hash(business_event_id, attempt_seq)` — explicitly **does not include `run_id`** (Temporal-assigned) so ContinueAsNew preserves idempotency. | T8 (temporal B-2) |
| **L11** | Put-call parity, calendar-spread bounds, strike homogeneity | Add metamorphic relations: **vega convexity ≥ 0 at ATM**, **forward-rate consistency** $f(t,T_1,T_2)\cdot DF(T_1) = DF(T_1) - DF(T_2)$, **Greeks-bumping = Greeks-AD at small bumps to 2nd order**, **local-vol round-trip no-arb residual ≤ τ**. | E.1 |
| **L12** | Admissibility closure | Replace rejection-sampled `gen_calibrated_state` with **MCMC / Hamiltonian sampling on the admissibility manifold** so tests do not degenerate to no-op when $\Theta_{AF}$ is tight. | E.3 |
| **L13** | Bounded liveness via simulation | Reclassify from "unwitnessed" to "**witnessed via composition**": (a) **TLA+ Büchi automaton** for liveness in the obligation FSM, (b) **bounded-horizon simulation** with `env.compensation_window` parametrised in L7 / L21. Surrogate parameters all pinned. | T7 (testcommittee F15/F16) |
| **L14** | Capability scope with replay parity | Strengthen oracle: replay queries demonstrate **the same audit envelope as production**, including a **runtime-checked phantom-type witness** of capability admission (not merely a static type-check). | C.5 |
| **B11** boundary | Captured attestation replay; assumed historical key registry | **Structural invariant**: public verification keys are **append-only**; HSM rotation means *adding* a new key, never removing the old. Documented as the cryptographic contract the data layer requires from the security layer. | A.3 |

**New law (additive only).** L15 — Novation Bridge Conservation (see §1.15
below). **L1–L14 retained**; numbering preserved.

### §0.2 — Boundary catalogue: 12 → 17 boundaries

Added: **B13** floating-point determinism (BLAS pin, thread-count pin,
`fp:strict`); **B14** persistent-storage iteration order (canonical sort
before any aggregation); **B15** intra-handler concurrency (canonical-order
reduction over activity completions); **B16** Unicode/locale (NFC + UTF-8
canonical bytes at parser ring); **B17** test-environment seed (seed derived
from `git_sha(test_corpus) + cdm_version`; failed shrinks committed as
artefacts). Per Round-1 boundary audit: any number lower than 17 must be
justified by demonstrating structural unreachability of the corresponding
non-deterministic source; no such demonstration exists for the five added.

### §0.3 — Fault catalogue: 49 rows → 49 rows + 4 missing harnesses specified

The 7-cluster × 7-fault structure is preserved. **What changed:** every row
now names a **harness** (test fixture, simulator, or fault injector) that
exercises it; previously several rows named only a *detection mechanism*
without a test that verifies the detection fires. Specifically:
- **Cluster V silent-corruption.** New harness: `corrupt_byte_in_move_blob`
  fixture; assert chain-verification flags it.
- **Cluster IV partition.** New harness: `gateway_down(duration =
  max_silence + ε)`; assert obligation escalation fires; `max_silence`
  pinned per oracle in L7.
- **Bugification harness.** New: `gen_adversarial_legal` generator family
  emitting zero-balance moves, max-precision Decimals, leap-second clock
  advances, near-singular Hessians, near-zero correlation matrices.
- **L4 clock-skew interleaving harness.** New: $(t_v, t_k)$ pairs
  generated with arbitrary interleaving; vendor-old + ingestion-new
  paired against vendor-new + ingestion-older.

### §0.4 — Goodhart traps: 4 → 5, with concrete detection mechanisms

| Trap | v1 mitigation | v2 detection mechanism |
|---|---|---|
| Snapshot stub-swap | "P-L8 byte-identical replay" | **NEW** boundary-integrity production test: pull N committed transactions from the *production* snapshot store; replay against the production handler binary; assert byte-identical. Runs nightly in staging-mirror. |
| Mutation set exclusion | M-CDM, M-CANON, M-LATE mandatory | **Mutation-survivor reporting**: every CI run lists every surviving mutant, why it survived, and which property is too weak; survivors are findings, not tail allowance. **Stratified kill-rate targets**: 90% in event handlers, 90% in canonicalisation/hash code, 85% in pricing kernels, 80% overall. |
| Biased generators | Stratified per CDM ProductType × EventIntent | **Per-stratum coverage targets** (first-class assertions, not aspirational): 5% of `gen_market_snapshot` within ε of arbitrage boundary; 10% of `gen_obligation` deadline-within-current-sim-clock + δ; 10% multi-CCP positions; 5% manufactured-payment-cross-jurisdiction; 3% near-singular calibration Hessians. CI fails if a target is missed. |
| Aggregation-masking | "Per-(scope) check mandatory" | **Meta-property test**: synthesise a violation that nets to zero under the aggregate; assert the per-scope check catches it. Run as a property whose property is "the property catches the bug." |
| **NEW — Type-system witness laundering** | (none in v1) | **Runtime checker** fires on every write attempt to any field guarded by a phantom-typed witness (`arbitrage_certificate`, `snapshot_certificate`, `capability_witness`); **adversarial Hypothesis test** attempts to construct values inhabiting the witness type via reflection/`__post_init__` bypass; all witness types have enumerated construction sites, consumers, and elimination sites. |

### §0.5 — Mutation operator set: 10 → 15

Added in v2 per testcommittee C.2:
- **M-FAKE-CERT**: emit a `certified=True` calibrated state without running
  $\Theta_{AF}$ projection — kills L11/L12 if oracle is sharp.
- **M-AGGREGATE**: replace per-scope conservation check with global-scope
  check — kills L7 (per-CCP), L6 (per-mandate), and the new aggregation-
  masking meta-property.
- **M-DEFLATE**: silently round/truncate Decimal in a state-delta — kills
  L5/L6/L7 if oracle is bit-equal but survives if oracle uses tolerance.
- **M-BIAS**: skew a generator stratum to common cases — should be killed
  by per-stratum coverage assertions (this is a *meta-mutation* against
  the test program itself).
- **M-SHRUG-RETRY**: convert a non-retryable error to retry-with-success
  — kills L13 (obligation should escalate, not retry-shrug) and L14
  (capability denial is non-retryable).

### §0.6 — Property-test pyramid

Declared shape, per-layer counts (targets, not floors of less-is-acceptable):
- **L0 cross-cutting invariants** (P-CCC-1 through P-CCC-6): 6 properties,
  ≥ 1 assertion per committed transaction (continuously verified).
- **L1 per-law properties** (P-L1 through P-L15): 15 properties,
  Hypothesis target ≥ 10⁵ examples per nightly run, per-stratum coverage
  targets enforced.
- **L2 metamorphic / fault-injection** (M1–M9 below): 9 fault families,
  Hypothesis target ≥ 10⁴ examples per nightly run.
- **L3 mutation testing** (M-CONS, M-BOUND, ..., M-SHRUG-RETRY): 15
  operators, kill-rate targets stratified per code region.
- **L4 boundary-integrity production** (1 nightly job): 1 job that pulls
  production state and round-trips it; binary pass/fail per night.

The **shape** is pyramid-classical: many cheap cross-cutting checks at the
base, fewer expensive end-to-end production checks at the apex. The
*Goodhart-trap*-shaped inversion (lots of unit tests, no end-to-end checks)
is forbidden by the L4 layer's existence.

---

## §1 — Cross-Layer Consistency Laws (the catalogue, **v2 with strengthened oracles**)

A *cross-layer* consistency law is one whose precondition mentions data in
one category (or layer) and whose postcondition mentions data in another. I
enumerate **fifteen** such laws (one new bridging law in v2). Each carries
(i) precondition, (ii) postcondition, (iii) data categories tied together,
(iv) the failure mode forbidden, (v) the witnessing strategy with an
**oracle strength** annotation (Universal / Structural / Safety / Domain /
Speculative — the property ramp).

The laws are clustered into five groups: **L1–L4 lineage / oracle**,
**L5–L7 + L15 conservation / accounting**, **L8–L10 determinism / replay**,
**L11–L12 calibration / valuation**, **L13–L14 settlement / liveness**.

### L1 — Lineage Closure (every committed move has a primary-attested observable in its lineage), **with retention as structural invariant**

- **Precondition.** A `pending_tx` is emitted by handler $h$ with input set
  $I = (\text{state}, \text{ProductTerms}[u], \text{snapshot})$.
- **Postcondition.** After commit, the transaction's metadata resolves
  every observable referenced in $I$ to a content-addressed *attestation
  envelope* whose `source_signature` was verified at ingestion. **Every
  snapshot referenced by a non-terminal `ValuationRecord` is retained until
  that record reaches a terminal lifecycle state.** FSM transition
  `Stale → Pricing` is **gated** on `lineage_walk_succeeds(record)` —
  the gate is a structural invariant of the executor, not an operational
  promise.
- **Data categories tied.** Market (3), Oracle (4), Settlement
  Infrastructure (7), Calibrated Latent State (8), Smart-Contract
  Execution (5), Provenance (11). **Plus retention metadata in L21 / L22**.
- **Failure mode forbidden.** A *floating* observable (the v1 mode) **plus**
  *retention/re-entry race*: a snapshot collected between FIRM emission
  and `Stale → Pricing` re-entry. The latter was the Round-1 BLOCKING
  finding A.1.
- **Oracle strength.** Structural (gate is type-enforced) + Universal
  (no commits without lineage closure).
- **Witnessing.** Pre-commit `lineage_walk(tx)` predicate; integration
  test `test_stale_to_pricing_does_not_garbage_collect_snapshot` forces
  GC then attempts FSM re-entry, asserts gate denies. **Decidable**.
- **Property sketch.**
  ```python
  @given(tx=gen_committed_tx_with_revaluation_cycle())
  def test_lineage_closure_under_fsm_reentry(tx):
      assume(tx.fsm_path_includes("Stale", "Pricing"))
      for record in tx.valuation_records:
          if not record.is_terminal:
              assert snapshot_store.exists(record.attestation_snap)
              assert lineage_walk(record).all_envelopes_signed()
  ```

### L2 — Snapshot Determinism Closure

(Unchanged in substance from v1; oracle now explicitly bit-identical under
Decimal arithmetic and Mahalanobis-zero under MC with seeded MCMC.)

- **Witnessing.** Replay test from snapshot. **Decidable** for
  deterministic pipelines; **probabilistic-with-bounded-ε** for MC pipelines
  (seed = `hash(snapshot_id, unit_id, model_version)`; MCMC chain
  diagnostic stationarity assertion).

### L3 — Settlement-Move Closure

(Unchanged from v1 in substance; oracle now also asserts CSDR penalty
obligation if `end_to_end_id` resolution fails by `intended_settlement_date
+ N`.)

### L4 — Bitemporal Coherence, **with bounded restatement chain witness**

- **Precondition.** Any datum $d$ in Categories 2, 3, 4 carries
  `(vendor_time, knowledge_time, effective_time)`.
- **Postcondition.** $\text{vendor\_time}(d) \le
  \text{knowledge\_time}(d)$, and `read(id, as_of_knowledge=t_k,
  as_of_vendor=t_v)` is total whenever a registered version with vendor
  time $\le t_v$ has $\text{ingestion\_time} \le t_k$. **Furthermore**,
  for every restatement chain $v_1 \to v_2 \to \dots \to v_n$ with
  $n \le \kappa_{\text{restate}}$ (pinned in L7/L21), bitemporal replay
  is total by induction on $n$.
- **Failure mode forbidden.** Bitemporal collapse (v1) **plus**
  *clock-skew interleaving*: $(t_v^{\text{old}}, t_k^{\text{new}})$ paired
  with $(t_v^{\text{new}}, t_k^{\text{old}})$ in a way that breaks total
  ordering of restatement effects.
- **Oracle strength.** Safety + Structural (induction on $n$).
- **Witnessing.** Hypothesis generator emits arbitrarily-interleaved
  $(t_v, t_k)$ sequences up to depth $\kappa_{\text{restate}}$; replay
  is asserted total. The harness is **fault-injecting**: late vendor
  publications are simulated by reordering the message bus.
- **Property sketch.**
  ```python
  @given(chain=gen_restatement_chain(max_depth=KAPPA_RESTATE),
         interleave=gen_clock_skew_permutation())
  def test_bitemporal_total_under_skew(chain, interleave):
      reordered = interleave.apply(chain)
      for (t_v, t_k) in cross_product_axes(reordered):
          if t_v <= t_k:
              v1 = read(chain.id, as_of_knowledge=t_k, as_of_vendor=t_v)
              v2 = read(chain.id, as_of_knowledge=t_k, as_of_vendor=t_v)
              assert v1 == v2
  ```

**Reclassification.** v1 listed L4 in U2 unwitnessed (unbounded vendor
restatement chains). v2 reclassifies as **witnessed by induction** under
the bounded-chain assumption $n \le \kappa_{\text{restate}}$, with the
operational guard (snapshot retention exceeds longest-tenor unit) named
in L21. Residual risk reduces to "$\kappa$ chosen too small" — a tuning
parameter, not an unwitnessed law.

### L5 — Per-Event-Class Conservation (StatesHome C2 lifted)

(Strengthened oracle.) For every additive monotone field $f$:
$\sum_w \Delta f(w, u) = 0$ per event class $c$, **with the empty-holder-set
base case enforced by structural type construction** (`PositionState[w,u]`
defaults to vacuous-zero by the type system, not by handler logic — kills
M-VACUOUS structurally).

### L6 — Mandate-as-Unit Conservation, **with structurally-typed FeeReserve**

(Strengthened oracle.) HWM state lives **only** at `PositionState[w,
u_MA]`; the firm's `fee_reserve` is structurally typed `FeeReserve`
(refined wallet sum-type), not a free `Wallet`. Routing fees into a
non-conservation field is a type error, not a runtime one.

### L7 — Per-CCP Conservation Scope

(Unchanged in substance from v1 except composition with L15 below.)

### L15 — Novation Bridge Conservation (NEW)

- **Precondition.** A `BusinessEvent ∈ Novation_Set` is committed,
  re-binding contract $u$ from CCP $A$ to CCP $B$ (or from
  counterparty $X$ to counterparty $Y$ in non-cleared novation).
- **Postcondition.** Either (a) **single-tx novation**: the union scope
  $\{A, B\}$ satisfies $\sum_w \sum_{ccp \in \{A,B\}} \Delta \text{ac}(w,
  u, ccp) = 0$, **and** per-CCP scope is permitted to fail per-leg
  (this is the *bridge exception* explicitly carved out from L7); OR
  (b) **two-tx decomposition**: the novation is split into two atomic
  transactions, with an explicit `Obligation` of class
  `NovationBridge` registered between them whose `discharge_predicate`
  is satisfaction of the second leg. Per-CCP scope holds in each leg
  independently.
- **Data categories tied.** Reference (2.7 CCP master) ↔ Listed (6.2 CCP
  binding) ↔ PositionState ↔ Move stream ↔ Obligation (D8).
- **Failure mode forbidden.** *Silent bridge*: per-CCP conservation
  appears to fail because the cross-CCP flow is not registered as a
  bridge; in this case L7 alarms but the system is actually correct, and
  operators learn to suppress the alarm — a Goodhart trap of its own.
- **Oracle strength.** Structural (sum-type on `BusinessEvent` enforces
  bridge tag).
- **Witnessing.** Property test: every commit of a Novation_Set event
  either (a) carries an `is_novation_bridge=True` tag and satisfies
  union-scope conservation, or (b) is the first/second leg of a
  bridge-pair with a registered Obligation.
- **Property sketch.**
  ```python
  @given(ev=gen_novation_event(), trades=lists(gen_cleared_trade()))
  def test_novation_bridge_conservation(ev, trades):
      tx = handler_for(ev)(apply_all(trades), ev)
      if tx.is_novation_bridge:
          # union scope
          ccps_touched = {d.ccp for d in tx.state_deltas}
          for f in MONOTONE_FIELDS:
              union_sum = sum(d.delta(f) for d in tx.state_deltas
                              if d.ccp in ccps_touched)
              assert union_sum == 0
      else:
          # must be a registered bridge half
          bridge = obligation_store.find_bridge_half(tx.tx_id)
          assert bridge is not None
          assert bridge.bridge_tx_pair_intact()
  ```

### L8 — Replay Determinism, **with three-engine, adversarial-completion, bit-identical-pricer oracle**

(Strengthened oracle.) Re-execution produces a `pending_tx` $T'$ with
`tx_id(T') == tx_id(T)` and bit-identical moves and state deltas, **under
all of**: (a) two distinct storage backends with different iteration order
(B14); (b) adversarial activity-completion ordering (B15); (c) pinned
BLAS / pinned thread count / `fp:strict` for any FP pricers in the path
(B13); (d) NFC-canonicalised UTF-8 for all string fields (B16); (e) test
seed derived from `git_sha + cdm_version` (B17).

**Reclassification of U4 (cosmic-ray).** v1 left U4 weakly witnessed; v2
**bounds** the residual probability $\epsilon = \epsilon(n, k, R, \tau)$ as
a function of erasure-coding $(n,k)$, replication factor $R$, and
re-verification cadence $\tau$. With explicit $\epsilon$, the law is
witnessable by hardware-fault simulation with the same harness pattern as
the bug-injection harnesses; "operational tolerance" is now a numerical
target, not a hand-wave.

### L9 — Forgetful-Functor Composition, **with dependence-relation lattice**

(Strengthened oracle.) The dependence-relation lattice
$\mathcal{D} = \{\text{trade-lineage}, \text{timestamp-order},
\text{snapshot-shared}, \text{capability-shared}\}$ partitions event pairs.
Composition law $F(e_2 \circ e_1) = F(e_2) \circ F(e_1)$ is asserted **per
partition**: free composition for events sharing no $\mathcal{D}$-relation;
ordering-token-enforced composition for events sharing trade-lineage or
timestamp-order; cross-checked composition for events sharing snapshot or
capability.

### L10 — Workflow-History Replay Coherence, **with `tx_id` independence from `run_id`**

(Strengthened.) `tx_id = canonicalise_hash(business_event_id, attempt_seq,
moves, state_deltas)` — **does not include `run_id`**. ContinueAsNew
preserves idempotency keys. Workflow history determinism is asserted under
B17 (test-environment seed) with adversarial worker-restart timing.

### L11 — Calibration / Valuation Model Consistency, **with extended metamorphic catalogue**

(Strengthened oracle.) In addition to v1's put-call parity, calendar-spread
non-negativity, strike homogeneity:

- **Vega convexity at ATM**: $\partial^2 V / \partial \sigma^2 \ge 0$ for
  European calls at $K = F$.
- **Forward-rate consistency**: $f(t, T_1, T_2) \cdot DF(T_1) = DF(T_1)
  - DF(T_2)$ within tolerance — known to fail under non-monotone curve
  interpolation; this property catches it.
- **Bumping = AD at small bumps to 2nd order**: $|\partial^k V /
  \partial x^k_{\text{bump}} - \partial^k V / \partial x^k_{\text{AD}}|
  \to 0$ as bump $\to 0$, for $k \in \{1, 2\}$.
- **Local-vol round-trip**: calibrate to surface, reprice surface, check
  $\max_{\text{strike, expiry}} |\sigma_{\text{repriced}} -
  \sigma_{\text{input}}| < \tau_{\text{LV}}$ AND no-arb residual on the
  reproduced surface $< \tau_{\text{NA}}$.
- **Greeks-via-bumping = Greeks-via-AD on Jacobian**: Jacobian recovers
  price under Taylor expansion to second order on small perturbations
  (v1) extended to second-order Greeks.

### L12 — No-Arbitrage Admissibility Closure, **with Hamiltonian-MC sampler**

(Strengthened.) `gen_calibrated_state` uses **Hamiltonian Monte Carlo on
the admissibility manifold** (rejection-sampling fails under tight
$\Theta_{AF}$ in high dimensions per E.3); state-space exploration of
near-boundary cases is parametrised by the per-stratum coverage target
"5% of `gen_calibrated_state` outputs land within $\epsilon_{AF}$ of the
boundary."

### L13 — Obligation Liveness Closure, **reclassified as witnessed-via-composition**

- **Precondition.** An `Obligation` $o$ with `deadline = t_d` and
  `discharge_predicate = δ`.
- **Postcondition.** $\forall t > t_d.\ o.\text{state} \in
  \{\text{Discharged}, \text{Compensated}, \text{Defaulted}\}$, witnessed
  by **composition of three artefacts**:
  1. **TLA+ Büchi automaton** for the obligation FSM proving liveness
     (every reachable state has a path to a terminal state) — *type-of-
     witness*: model-checker proof up to bound $T_{\max}$.
  2. **Bounded-horizon simulation** with `env.compensation_window`
     pinned in L7 — *type-of-witness*: property test under virtual clock.
  3. **Production observability**: per-obligation freshness map; alert
     fires if an obligation rots in `Pending` past `deadline +
     escalation_horizon` — *type-of-witness*: runtime audit.
- **Reclassification.** v1 listed L13 in U1 unwitnessed; v2 reclassifies
  as **witnessed by composition (1)+(2)+(3)** with all surrogate
  parameters pinned (consensus quorum, retention horizon, erasure-coding
  $(n,k)$, bounded-horizon length, escalation horizon).
- **Property sketch.**
  ```python
  @given(o=gen_obligation_with_extreme_deadline(),
         env=gen_simulation_horizon_with_max_silence_partition())
  def test_obligation_terminates_under_partition(o, env):
      sim = run_until(env, deadline=o.deadline +
                          env.compensation_window +
                          env.escalation_horizon)
      final = sim.obligation_state(o.id)
      assert final in {Discharged, Compensated, Defaulted}
      # And: a partition for max_silence + ε must fire escalation
      if env.partition_duration > MAX_SILENCE[o.oracle_class]:
          assert sim.escalation_fired(o.id)
  ```

### L14 — Capability-Scope Closure, **with runtime-checked phantom witness**

(Strengthened oracle.) Every read of `(w, u)` PositionState row, every
write of a `(w, u)` field, and every replay query is gated on $\mathcal{C}_t$
**by a runtime-checked phantom-typed witness** `CapabilityWitness(c, q,
t)`, constructed only via the gateway, consumed only by the storage layer.
The witness type's **construction sites**, **consumer sites**, and
**elimination sites** are enumerated in a closed inventory; an adversarial
Hypothesis test attempts to construct values bypassing the gateway via
`__init__`, `__post_init__`, `__new__`, dataclass `__replace__`, or
reflection — assertion: every such attempt raises `TypeError` or
`PermissionError`.

---

## §2 — Determinism Boundary Catalogue (12 → **17**)

A *determinism boundary* is any place external/non-deterministic input
enters the system. **Every boundary in this list MUST be injectable in the
simulation harness.** Any boundary outside this list reaching a handler is
a structural failure of the catalogue.

### B1–B12 (unchanged from v1; brief restatement)

- **B1** Wall-clock reads — boundary captured by `Clock` interface;
  replay reads from history.
- **B2** Random/entropy — `seed = hash(snapshot_id, unit_id,
  model_version)`; UUIDs derived from `tx_id`.
- **B3** External price/FX/vol feeds — `MarketSnapshot` content-addressed
  bundle.
- **B4** External event oracles — Attestation envelope; signature
  verification at gateway; **public verification keys are append-only**
  (v2 strengthening per A.3).
- **B5** Reference data — bitemporal versioned envelopes.
- **B6** Settlement infrastructure — boundary-mocked enrichment, content-
  addressed in production.
- **B7** Calibration filter state — checkpointed `(x_{t|t}, P_{t|t},
  certified, ar_region_id)`.
- **B8** Workflow scheduling — Temporal `WorkflowHistory`.
- **B9** CDM enum universe — `cdm_version` pinned per workflow input.
- **B10** Hash algorithm / canonicalisation — algorithm and version in
  every hash; canonicalisation pinned (RFC 8785 JCS / Protobuf canonical
  with field-tag pin / CBOR per RFC 8949 §4.2.1; choice declared in L21).
- **B11** Operator/human interaction — signed governance attestation
  envelope; **append-only public-key registry** (v2 strengthening).
- **B12** Network/message reordering — `(idempotency_token,
  source_publication_time, ingestion_time)` triple; replay in
  ingestion-time order.

### B13 (NEW) — Floating-point determinism

- **Entry points.** Pricing kernels (BLAS, LAPACK, FFT, MC), risk
  Jacobians, sensitivity computations.
- **Boundary captured by.** L21 axes `blas_pin: BlasImplVersion`,
  `thread_count_pin: int`, `fp_strict: bool` (compiler flag pinned per
  module). Reductions (`sum`, `dot`) use **canonical-order reduction**
  (sort by index before sum); FMA fusion pinned per architecture.
- **Replay.** Re-run with pinned BLAS + pinned threads + same OS/glibc
  version (recorded in L22 anchor). Property: `test_pricer_bit_identical_
  cross_blas_impl(snap)` runs the pricer under two pinned BLAS impls
  with identical inputs, asserts `==` byte-equal output (or, if
  cross-impl bit-equal is infeasible, asserts both fall within
  $\tau_{\text{FP}}$ of a Decimal reference).

### B14 (NEW) — Persistent storage iteration order

- **Entry points.** Any handler that iterates a `PositionState` set,
  obligation set, or oracle attestation set and feeds the iteration
  result into a hash, sum, or canonicalisation.
- **Boundary captured by.** Mandate: every set/map iteration in handler
  code is preceded by canonical sort (`sort_key` documented per type).
  L21 axis `storage_engine_pin` records which backend was used.
- **Replay.** Property: `gen_state_with_two_storage_engines` runs the
  same handler twice (RocksDB and Postgres) and asserts
  `tx_id_engine_A == tx_id_engine_B`.

### B15 (NEW) — Intra-handler concurrency

- **Entry points.** Handlers that fire concurrent activities (e.g.,
  parallel SSI lookup + party master lookup).
- **Boundary captured by.** Mandate: every multi-result reduction is over
  a canonical order (sort by `activity_seq`, never by completion order).
  No `asyncio.as_completed` in handler reduction code; only
  `asyncio.gather` with sorted post-processing.
- **Replay.** Simulator delivers activity completions in adversarial
  orders; property `test_handler_invariant_to_completion_order(snap)`
  runs the handler under all permutations of completion timing and
  asserts byte-equal output.

### B16 (NEW) — Locale / encoding / Unicode normalisation

- **Entry points.** Free-text-like fields: legal entity names,
  free-form addresses inside SSI metadata, ISDA Master party legal name,
  product comments.
- **Boundary captured by.** **NFC + UTF-8-byte canonicalisation** at
  every parser ring boundary. Non-NFC inputs are normalised at ingress
  and the *normalised* bytes hashed; the original is preserved alongside
  in the envelope.
- **Replay.** Property:
  `test_party_lookup_invariant_under_nfd_input(party)` constructs the
  same party under NFD vs NFC encoding and asserts
  `lei_resolved_id` and `tx_id` are equal.

### B17 (NEW) — Test environment as boundary

- **Entry points.** The test runner itself (Hypothesis seed, parallel
  test workers, OS-scheduled order of fuzzed inputs). The simulator-
  determinism mirror of B1.
- **Boundary captured by.** Test seeds derived from
  `seed = hash(git_sha(test_corpus), cdm_version)`. Failed shrinks
  committed to the test artefact directory. CI artefact:
  `(seed, repro)` for every successful run, archived for at least
  $\tau_{\text{shrink-replay}} = 90$ days.
- **Replay.** Replay any failing CI run from the archived
  `(seed, repro)` pair. Property: `test_seed_pinning_replays_identically`
  asserts that the same seed produces the same Hypothesis example under
  the same `cdm_version`.

**Boundary count: 17.** A future round may justify a count lower than
17 only by demonstrating structural unreachability of the corresponding
non-deterministic source (e.g., "we have no FP pricers" — false today;
"we use only one storage engine" — defensible if pinned in L21 but the
boundary still exists). Until that demonstration is made, any number
lower than 17 fails the audit.

---

## §3 — Fault Catalogue per Data Cluster (49 rows + harnesses)

The 7-cluster × 7-fault structure is preserved from v1. **What is new
in v2:** every row now names a **harness** that exercises it.

The standard taxonomy: missing, late, duplicated, contradicted,
mis-attributed, silent-corruption, partition.

(Tables for Clusters I–VII unchanged from v1 in their detection / recovery
columns. The **harness column** is new in v2; only the harness column is
shown below to save space. Every detection mechanism from v1 is preserved.)

### Cluster I — Identity & ProductTerms — harnesses

| Fault | Harness |
|---|---|
| missing | `gen_handler_with_missing_master_ref` |
| late | `gen_bitemporal_late_master_update` |
| duplicated | `gen_double_registration_attempt` |
| contradicted | `gen_cross_source_master_disagreement` |
| mis-attributed | `gen_master_typo_corrected_via_correction` |
| silent-corruption | `corrupt_byte_in_master_blob` |
| partition | `simulate_gateway_down(duration)` |

### Cluster II — Calendars/Conventions — harnesses

(omitted for space; pattern as Cluster I — every fault has a generator
or simulator pair with assertion of detection mechanism firing.)

### Cluster III — Market Observables — harnesses

(omitted; same pattern; **partition** harness uses
`simulate_feed_partition(duration = max_silence + ε)`.)

### Cluster IV — Oracle/External Event Attestations — harnesses

| Fault | Harness |
|---|---|
| missing | `gen_event_with_no_inbound_attestation` |
| late | `gen_late_credit_event` (post-deadline) |
| duplicated | `gen_double_event_publication` |
| contradicted | `gen_dc_redecision_chain` |
| mis-attributed | `gen_issuer_event_with_typo` |
| silent-corruption | `corrupt_signature_byte` (must reject) |
| **partition** | `simulate_oracle_silence(duration > max_silence[oracle_class])` — must fire obligation escalation; `max_silence` per oracle class pinned in L7 |

### Cluster V — Smart-Contract Execution & Move Stream — harnesses

| Fault | Harness |
|---|---|
| missing | `gen_workflow_emit_with_dropped_move` |
| late | `gen_post_commit_emit_delay` |
| duplicated | `gen_double_emission_attempt` (same `tx_id`) |
| contradicted | `gen_two_replicas_diverging_bytes` |
| mis-attributed | `gen_misattributed_scope_delta` |
| **silent-corruption** | `corrupt_byte_in_move_blob` — must trip chain verification on next pre-commit lineage walk; **this harness is now mandatory** (closes Round-1 D.1 BLOCKING) |
| partition | `simulate_executor_partition(duration)` |

### Cluster VI — Calibration Latent State — harnesses

(omitted for space; partition harness fires FSM `Stale` transition;
silent-corruption harness verifies $\Theta_{AF}$ projection re-projection
detects the corrupted state.)

### Cluster VII — Orchestration / Settlement / Obligations — harnesses

(omitted; partition harness uses
`simulate_custodian_partition(duration > max_silence[CSDR])`,
asserts compensation path triggers and CSDR penalty obligation registers.)

### §3.bug — Bugification harness (NEW)

Antithesis-style **bugification** generators that emit
*pathological-but-legal* inputs:

- `gen_zero_balance_move`: a move with `quantity = 0` (legal under
  type system; structurally forbidden by C-CCC-5; harness must trigger
  pre-commit reject).
- `gen_max_precision_decimal`: a Decimal at the largest representable
  precision; harness verifies canonicalisation does not silently
  truncate (M-DEFLATE).
- `gen_leap_second_clock_advance`: a clock advance that crosses a
  leap-second boundary; harness verifies day-count and accrual
  arithmetic survive.
- `gen_near_singular_hessian`: a calibration step with a Hessian whose
  smallest eigenvalue is within $\epsilon$ of zero; harness verifies
  the calibration FSM enters `Failed` rather than emitting an unstable
  posterior.
- `gen_near_zero_correlation_matrix`: a multi-asset surface with
  correlation $\to 0$; harness verifies pricers handle the singular
  limit deterministically.
- `gen_adversarial_legal_obligation`: an obligation with `deadline =
  current_clock + 1ns` (legal but bug-finding); harness verifies the
  timer fires deterministically.

Bugification harnesses run nightly. The four laws v1 listed as unwitnessed
(L1, L4, L8, L13) are precisely the ones bugification finds violations
in for free; with v2's reclassification (L4, L8, L13 reclassified as
witnessed), bugification provides an *additional* assurance layer.

---

## §4 — Property-Based Testing Program (refined)

### §4.1 Generators — per-stratum coverage targets (NEW)

The closed generator universe (v1) is refined with **per-stratum coverage
targets**, each a first-class assertion (CI fails if not hit):

| Generator | Stratum | Target | Rationale |
|---|---|---|---|
| `gen_market_snapshot` | within $\epsilon_{AF}$ of arbitrage boundary | ≥ 5% | exercise L12 boundary |
| `gen_market_snapshot` | extreme vol (>3σ from running mean) | ≥ 3% | exercise L11 |
| `gen_obligation` | deadline within `current_sim_clock + δ` | ≥ 10% | exercise L13 timer-fire |
| `gen_oracle_event` | late (`source_pub_time` < `ingestion_time` by ≥ 1 day) | ≥ 5% | exercise L4, L9 |
| `gen_cleared_unit` | multi-CCP | ≥ 10% | exercise L7, L15 |
| `gen_calibrated_state` | near-boundary (HMC-sampled) | ≥ 5% | exercise L12 |
| `gen_workflow_history` | length > 100 events | ≥ 10% | exercise L10 ContinueAsNew |
| `gen_cross_currency_qis_with_manufactured_payment` | full path | ≥ 5% | exercise L6, NS-3 manufactured-payment law |
| `gen_position_set` | size > 10⁴ | ≥ 3% | exercise B14 sort-before-iterate |

### §4.2 Properties (per-law sketches, see §1 for strengthened oracles)

P-L1 to P-L14 retained from v1 with strengthened oracles per §1. **P-L15
(Novation Bridge Conservation)** is new (sketch in §1.15 above).

### §4.3 Cross-cutting (lifted) properties

P-CCC-1 through P-CCC-6 retained. **NEW P-CCC-7:** Aggregation-masking
meta-property (testcommittee C.4):

```python
@given(state=gen_state(), violation=gen_aggregation_masking_violation(state))
def test_aggregation_does_not_mask(state, violation):
    # Synthesize a per-scope violation that nets to zero in aggregate.
    state_violated = apply(state, violation)
    # The aggregate check passes (that's the masking).
    assert aggregate_conservation(state_violated)
    # The per-scope check MUST catch it.
    assert not per_scope_conservation(state_violated)
```

### §4.4 Mutation operator set (10 → 15)

Retained from v1: M-CONS, M-BOUND, M-VACUOUS, M-CLOCK, M-CACHE, M-NOPROJ,
M-CANON, M-CDM, M-CAP, M-LATE.

**NEW in v2:** M-FAKE-CERT, M-AGGREGATE, M-DEFLATE, M-BIAS, M-SHRUG-RETRY
(definitions in §0.5).

**Reporting discipline.** Every CI run reports: (a) overall kill rate,
(b) per-stratum kill rate (event handlers, canonicalisation, pricing,
orchestration), (c) **list of surviving mutants with rationale**. Survivor
list is a finding, not tail allowance. Targets: 90% in event handlers and
canonicalisation, 85% pricing, 80% overall.

### §4.5 Witness type inventory (NEW — closes Goodhart trap C.5)

Every phantom-typed witness in the system is registered:

| Witness type | Constructor sites | Consumer sites | Elimination sites | Runtime check |
|---|---|---|---|---|
| `arbitrage_certificate` | only `theta_af_project()` | pricing kernels | only at FSM `UNPRICED → PRICING` transition | every commit verifies `cert.in_region(state.x, state.constraint_version)` |
| `snapshot_certificate` | only `snapshot_store.commit()` | all replay paths | only at `tx_id` derivation | every replay verifies `snap.content_hash == hash(snap.bytes)` |
| `capability_witness` | only `capability_gateway.grant()` | all storage writes/reads | only at audit-envelope emission | every write verifies witness chain back to gateway grant |
| `lineage_certificate` | only `pre_commit_lineage_walk()` | only at FSM gating | only at FSM `Stale → Pricing` | every transition verifies all envelopes signed |
| `bridge_witness` (NEW with L15) | only `novation_bridge_gateway()` | only at L15 oracle | only when bridge-pair tx-pair is intact | every novation verifies pair intact |

Adversarial Hypothesis test:

```python
@given(witness_type=sampled_from(WITNESS_TYPES),
       construction_method=sampled_from(BYPASS_METHODS))  # __init__,
                                                          # __post_init__,
                                                          # __new__,
                                                          # __replace__,
                                                          # reflection
def test_witness_type_unforgable(witness_type, construction_method):
    with pytest.raises((TypeError, PermissionError)):
        construction_method.attempt(witness_type)
```

---

## §5 — The Unwitnessed-Event Problem (4 laws → **1 genuinely unwitnessed**)

v1 listed 4 unwitnessed laws (U1–U4). v2 reclassifies three of the four:

| ID v1 | Law | v1 status | v2 status | Reason |
|---|---|---|---|---|
| U1 | L13 (liveness) | unwitnessed | **witnessed-by-composition** | TLA+ Büchi automaton + bounded-horizon simulation + production observability; all parameters pinned |
| U2 | L4 (bitemporal under unbounded chain) | unwitnessed | **witnessed-by-induction** | bounded-chain length $\kappa_{\text{restate}}$ pinned in L7; induction proof sketch in §1.4 |
| U4 | L8 (cosmic-ray) | weakly witnessed | **witnessed-with-bound-ε** | erasure-coding $(n,k)$ + replication $R$ + re-verification cadence $\tau$ all pinned; residual ε bounded |
| U3 | L1 (vendor opacity) | weakly witnessed | **U1 (genuinely unwitnessed)** | the surrogate is a *reduction* (trust-registry-truthful → lineage-closes); the trust assumption is the boundary |

**v2 unwitnessed count: 1.**

For the surviving U1 (L1 vendor opacity), the surrogate is a documented
reduction: assertions are made conditional on the trust-assumption
registry (NAZAROV CC-7) being truthful. Mitigations: multi-source
aggregation (CC-3) where feasible; innovation-gating (Cluster III); the
new **N8 aggregation gate** (per Round-1 T7 finding) — L10 rows admitted
to L19 snapshots consumed by L13 MUST have passed multi-source aggregation
OR carry an explicit `single_source_authority_assumption_ref` to the
trust registry.

The N8 aggregation gate is itself a structural invariant (not an
operational one) per Round-1 nazarov B-1 finding: a reading without
aggregation outcome is a type error, not a runtime one.

---

## §6 — Goodhart Traps Specific to the Data Layer (4 → **5**)

v1 Traps 1–4 retained. **NEW v2 Trap 5:** Type-system witness laundering
(C.5 in Round-1 review).

| # | Trap | Detection mechanism (v2) |
|---|---|---|
| 1 | "Snapshot coverage = 100%" / stub-swap | **Boundary-integrity production test**: pull N committed transactions from production snapshot store, replay against production handler, assert byte-identical. Runs nightly. |
| 2 | "Mutation score is high" but mutation set incomplete | **Survivor reporting**: every CI run lists every surviving mutant; survivors are findings. **15 mandatory operators** (10 v1 + 5 new). |
| 3 | "Property catalogue is large" but generators biased | **Per-stratum coverage targets** as first-class assertions (§4.1). CI fails if any target is missed. |
| 4 | "Conservation passes everywhere" but aggregate-masking | **P-CCC-7 meta-property**: synthesise a violation that nets to zero in aggregate; assert per-scope check catches it. |
| **5 (NEW)** | "Type system enforces it" but Python phantom types are nominal | **Runtime checker** on every write attempt; **adversarial Hypothesis test** attempts construction via reflection / `__post_init__` / `__new__` / dataclass `__replace__`; **closed witness inventory** (§4.5). |

---

## §7 — Recommendations to NAZAROV / FORMALIS / MINSKY (v2)

(v1 recommendations retained; v2 adds.)

- **NAZAROV.** Adopt 7-cluster fault structure as a presentation axis
  orthogonal to the 6 floors. Adopt the **17-boundary catalogue** as a
  cross-cutting axis. Adopt the L15 Novation Bridge law as a first-class
  cross-layer constraint, not a §6 footnote. Adopt the **N8 aggregation
  gate** as a structural invariant on L10 → L19 transition.
- **FORMALIS.** Treat L1–L15 as theorems derived from I-axioms with
  proof obligations explicit per law. The Round-1 T2 finding stands —
  every theorem in v1 §8 is theorem-shaped, not a theorem; in v2 the
  proof obligations are at least *named* but not discharged. Phase-3
  must discharge them or admit them as axioms of the realism budget.
- **MINSKY.** Per-leaf type signatures with generator stubs **and**
  per-stratum coverage targets. Every phantom-typed witness must carry
  an explicit construction-site / consumer-site / elimination-site
  inventory.

---

## §8 — Closing

The 15 cross-layer laws (L1–L15) are the **load-bearing claim** of the
data layer. The 17-boundary catalogue is the determinism-discipline
contract — every boundary captured, every replay total. The 49-row fault
catalogue, now augmented with explicit harnesses, is the adversarial
budget. The single remaining unwitnessed law (U1 = L1 vendor opacity) is
the residual-risk envelope, surrogated by a documented reduction.

**v1 → v2 closure.** Three Round-1 BLOCKING findings discharged (A.1
retention horizon as structural invariant; A.2 L15 Novation Bridge
Conservation; A.3 append-only public-key contract). Five boundary
omissions closed (B13–B17). Five mutation operators added. Four fault
harnesses specified. One Goodhart trap added. Three of four unwitnessed
laws reclassified as witnessable.

I hold the boundary across layers. Phase 3 arbitration may rename or
re-cluster these laws; it may not drop one without explicit demonstration
that the failure mode it forbids is structurally unreachable.

— end of Phase 2 cross-layer correctness synthesis, **v2** —
