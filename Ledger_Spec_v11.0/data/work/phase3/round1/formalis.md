# FORMALIS Phase 3 Round 1 — Adversarial Review of `proposal_v1.md`

**Reviewer role.** Independent FORMALIS instance, fresh context. Author of
`phase2/formalis.md` is treated as input, not authority. Convergence
arbitration is a separate role; here, this committee attacks.

**Committee.** Leroy (Chair), Coquand, Huet, Paulin-Mohring, de Moura,
Avigad. Where a finding is owned by a particular member it is initialled.

**Stance.** *We do not verify that code runs. We verify that code is
correct.* The Phase 2 synthesis hides three classes of defect: (i)
theorems with unstated or vacuous proof obligations; (ii) totality claims
on accessor functions whose domains are themselves undefined; (iii)
"unwitnessed laws" asserted with surrogate strategies that confuse
*coverage* with *witness*. We attack all three.

**Severity scale (this document).**
- **BLOCKING** — a property the proposal explicitly claims is violated, or
  the proposal's structure precludes proving the property at all. Convergence
  is impossible until addressed.
- **UNMITIGATED MAJOR** — the proposal acknowledges the issue but the
  mitigation as written is insufficient or self-contradictory. Must be
  resolved or downgraded with explicit reasoning before convergence.
- **MINOR** — clarity, formal-notation, or boundary-of-claim issue. May be
  accepted with a documented rationale.

---

## §0 — Headline

The proposal is taxonomically clean and engineering-disciplined, but
**five of the six FORMALIS test gates are unmet**. The most severe defect
is that the *five "compositional theorems"* in §8 are not theorems —
they are typed claims whose hypotheses include the conclusion or whose
hypotheses are themselves undefined. The four "unwitnessed laws"
(§9.4) are not all genuinely unwitnessable: at least two are
witness-able but the proposal has chosen not to commit the engineering.
The 24-leaf taxonomy is **not closed under the operations the proposal
demands of it** (notably L7 Policy and L23 Capability, where mutation
discipline is asserted but not specified, and where the *boundary*
between leaf-as-data and leaf-as-runtime is not stated).

Grade: **C+ / Reject as written; iterate.** Convergence not achievable
without addressing at least every BLOCKING finding and every
UNMITIGATED MAJOR.

---

## §1 — BLOCKING findings (B1–B7)

### B1. Theorem 1 (Conservation Lifting) is circular as stated.

**Location.** `proposal_v1.md` §8.1 (compressing `phase2/formalis.md`
§6 Theorem 1, lines 626–635).

**Code.**
> Hypotheses. (D-CONS) The data layer satisfies: for every event class,
> the handler-emitted moves satisfy $\sum_w \Delta w(u) = 0$. (E-ATOM)
> The executor satisfies: every transaction is committed atomically.
> (D-IDX) Every move references a `RegisteredUnitId` and `RegisteredWallet`.
> Conclusion. The ledger satisfies global conservation:
> $\forall t \ge 0, \forall u.\; \sum_w \text{balance}(w, u, t) = \sum_w \text{balance}(w, u, 0) + \sum_e \Delta_e^{\text{ext}}$.

**Property violated.** A theorem must not have its conclusion as a
hypothesis. (D-CONS) is **per-event-class** zero-sum at the *handler*
boundary; the conclusion is per-time, per-unit zero-sum at the *ledger*
boundary. Avigad's induction sketch proceeds: "either the new
transaction preserves the sum (D-CONS handler-level) or is rejected
(E-ATOM)." This is precisely the conclusion. **No work is done.** The
proof would be valid if (D-CONS) were per-handler ZERO modulo
issuance, but (D-CONS) as stated is total zero (i.e., the handler emits
no externalities). Issuance handlers necessarily violate (D-CONS) —
they create units. The theorem's hypothesis fails for issuance.

**Counterexample.** Consider a ProductTerms-amendment handler producing
a Breaking-amendment-induced supersession: $u_{\text{old}}$ is retired
(quantity goes to zero in every wallet) and $u_{\text{new}}$ is issued
(quantity created externally). (D-CONS) at handler boundary requires
$\sum_w \Delta w(u_{\text{old}}) = 0$ AND $\sum_w \Delta w(u_{\text{new}}) = 0$
— which forces no fresh units of $u_{\text{new}}$, contradicting
issuance. Either (D-CONS) is mis-stated (it must be "modulo the
ISSUANCE event class") or the conclusion is wrong (the
$\Delta_e^{\text{ext}}$ term in the conclusion is unconstrained).

**Remediation.** Re-state Theorem 1 with three hypotheses, each
*independently checkable*:
1. (D-CONS-non-issuance): for every event class $c \notin \text{ISSUANCE}$, $\sum_w \Delta w(u) = 0$ at handler boundary.
2. (D-ISS): every issuance handler emits a single MoveStream entry of class ISSUANCE with $\Delta^{\text{ext}}$ recorded at the externality boundary, and no other moves on $u$.
3. (D-PARTITION): the closed sum `EventClass = {ISSUANCE} ⊔ ConservativeClasses`, and the type system enforces that handlers of class ISSUANCE produce only ISSUANCE-tagged moves.

Then the conclusion follows by induction on the hash chain, *not* on
the abstract set $\Sigma_{[0,t]}$. The Phase-2 author's appeal to
"$\Sigma_{[0,t]}$" begs the question of how $\Sigma$ is constructed —
which is the very thing being proved.

**Severity rationale.** Theorem 1 is the load-bearing theorem of the
balance-sheet substantiation argument. As stated it is circular. **BLOCKING.**

---

### B2. Theorem 2 (Replay Determinism Lifting) silently consumes the
hardest hypothesis.

**Location.** `proposal_v1.md` §8.2, drawing on `phase2/formalis.md`
§6 Theorem 2 lines 638–647.

**Code.**
> Hypothesis (E-WF). The workflow runtime (Temporal) replays workflow code
> deterministically given identical history; activities are memoised on `input_hash`.
> Conclusion. $\text{Replay}(t, \Sigma_{[0,t]}, \text{versions}) = \text{Original}(t)$ bit-identically.

**Property violated.** (E-WF) is **the conclusion**, restricted to the
workflow runtime. The proposal states (C-A9 in §6.A9) "Workflow-history
determinism" as an *unconditional guarantee* listed under U8, but
elsewhere (§9.4) it is correctly listed as a **conditional assumption**
owned by Temporal. The proposal cannot have it both ways. (Coquand:
"Determinism is not a coincidence; it is a contract. State the contract
once.")

**Counterexample.** Temporal's determinism contract holds **iff** the
workflow code respects the SDK rules. The Phase-2 author lists the SDK
rules at §5 Boundary 9 and §5 Boundary 10 but does not state which of
the proposed handlers actually satisfies them. Any handler that:
(i) iterates a Python `dict` constructed at workflow scope (pre-3.7
ordering, post-3.7 insertion-order which is not preserved across worker
restarts on certain Python implementations),
(ii) closes over a global mutable cell,
(iii) calls a non-memoized helper that invokes `time.time()`,
breaks (E-WF). The proposal does not enumerate the invariants the
handler code must satisfy to entitle (E-WF); it cites Temporal SDK
docs by reference.

**Remediation.** State (E-WF) as a *gate*, not a *given*: a static-analysis
or SDK-instrumentation discipline that **rejects** any handler unless
it provably satisfies the workflow-determinism rule set. Until such a
discipline is named (linter? Type checker? Whitelist of allowed
imports?), the theorem is *conditional on a discipline that is not
specified*. **BLOCKING.**

---

### B3. Theorem 3 (Obligation Liveness Lifting) requires totality of
$\kappa$ that the proposal does not establish.

**Location.** `proposal_v1.md` §8.3, drawing on `phase2/formalis.md`
§6 Theorem 3.

**Code.**
> Hypothesis (D-DD). The discharge predicate $D$ is total over reachable
> ledger states; the compensation action $\kappa$ is total.
> Conclusion. P21 (liveness): $\forall o, t > o.t_d.\; o.\text{state} \in \{\text{Discharged, Compensated, Defaulted}\}$.

**Property violated.** "Reachable ledger state" is undefined as a
type. The set of reachable ledger states grows monotonically with the
move stream; a discharge predicate written today against a finite
schema may become non-total as new event classes are introduced.
Totality of $\kappa$ over `Obligation → PendingTransaction` is asserted
in `phase2/formalis.md` §2 L12 T3 as `[type-level]`, but a pending
transaction must reference a `RegisteredUnitId` and a `RegisteredWallet`
that *exist at compensation time*. If the unit has been retired (Breaking
amendment) before the deadline, $\kappa$ is forced to either:
(a) target the superseded unit (violates referential integrity), or
(b) target the new unit (changes the obligation's economic object), or
(c) fail (totality violated).

**Counterexample.** SBL recall obligation on `borrowed quantity = 5`
of unit $u$. Before the recall deadline, $u$ undergoes a Breaking
corporate action: $u$ is retired, $u'$ is issued in 2-for-1 ratio. The
borrower now owes 10 of $u'$. The compensation action $\kappa$ must
transform the recall obligation. The proposal does not state what
$\kappa$ does — it merely asserts $\kappa$ is total.

**Remediation.** Either (i) prove $\kappa$'s totality by structural
induction on the closed list of event classes that can affect a
referenced unit between obligation creation and deadline, with explicit
$\kappa$ rules per (event_class, obligation_kind) pair (CORRECTNESS
§3 Cluster IV / VII gives the matrix; the proposal must populate it);
or (ii) re-state Theorem 3 with the additional hypothesis (D-OB-FROZEN)
"once an obligation is registered, no event in the move stream can
modify the obligation's *referenced object* without registering a
parallel obligation transformation". The proposal does not name (D-OB-FROZEN)
nor populate the $(event\_class, obligation\_kind) \to \kappa$ table.
**BLOCKING.**

---

### B4. Theorem 4 (Substantiation) is a definition, not a theorem.

**Location.** `proposal_v1.md` §8.4, drawing on `phase2/formalis.md`
§6 Theorem 4.

**Code.**
> Hypothesis (D-PROJ). Every D7 derived projection is a pure deterministic
> function of D1–D6.
> Conclusion. $Q(t) = \pi_Q(D_{1..6}(t))$.

**Property violated.** The conclusion is the *type signature* of (D-PROJ);
they are the same statement. The "balance sheet IS the ledger" claim is
not a theorem — it is a stipulation that the proposal will not maintain
$Q$ as a separate datum. (Leroy: "If your conclusion is your hypothesis
restated, you have stated a definition, not proven a theorem.")

**Counterexample.** What the proposal *should* be proving is: every cached
projection $\hat{Q}(t)$ stored as an optimisation equals $\pi_Q(D_{1..6}(t))$.
That is a *consistency theorem* between cache and source-of-truth, and
*it is not proven in the proposal*. The proposal merely says "regenerable"
(L11.W1) and offers a property-test: $\pi(\text{cache}_t) = \pi(\text{recompute}(t))$.
A property test is not a proof. The cache may be poisoned between commit
and read.

**Remediation.** Replace Theorem 4 with two theorems:
1. (T4a, **definitional**, no theorem-content): the projection $\pi_Q$ is
   defined as a pure function of D1–D6.
2. (T4b, **theorem**): for any cache implementation $\hat{Q}$, **if the
   cache invalidation discipline** $\text{Inv}$ satisfies $\text{commit}(e) \implies \text{Inv}(\hat{Q}, e)$
   for every $e$ that touches D1–D6, **then** $\hat{Q}(t) = \pi_Q(D_{1..6}(t))$.
   The proof obligation is the cache invalidation discipline, *which the
   proposal does not name*.

Until the cache invalidation discipline is named, Theorem 4 is vacuous.
**BLOCKING.**

---

### B5. Theorem 5 (No-Arbitrage Pricing Lifting) cites Θ_AF without
defining it as a closed sum.

**Location.** `proposal_v1.md` §8.5, drawing on `phase2/formalis.md`
§6 Theorem 5.

**Code.**
> Hypothesis (D-CAL). `CertifiedCalibration.state_vector ∈ Θ_AF`.
> Conclusion. $r \in \text{FirmRecord}(u, t) \implies r.\text{dirty\_price} = E^{\mathbb{Q}}[\text{payoff}(u) | \mathcal{F}_t]$
> in the certified-calibration measure $\mathbb{Q}$.

**Property violated.** $\Theta_{AF}$ is referenced as the "no-arbitrage
admissible region" but is not defined as a *type*. (Paulin-Mohring:
"From a constructive proof, one extracts a program. From an
undefined region, one extracts confusion.") The proposal cites
`valuation §5.6`; that source is not in the data spec's scope. A
data-spec-internal definition is required, because $\Theta_{AF}$ is
*model-dependent* (Black-Scholes admissible region ≠ Heston admissible
region ≠ SABR admissible region). The "Certified" witness must carry
a model identifier, and the no-arbitrage region must be retrieved
*from the model code* by `model_id` lookup. The hypothesis (D-CAL) does
not encode this — it treats $\Theta_{AF}$ as a single fixed set.

**Counterexample.** A Heston posterior is certified into Heston's
$\Theta_{AF}^{\text{Heston}}$. A downstream pricer uses a SABR model on
the same posterior. (D-MOD) requires `Jacobian.model_id =
ValuationRecord.model_id`, which catches this. But what if the *same*
model-class admits multiple constraint versions (Heston-2018 vs
Heston-2024 with stricter constraint)? The proposal admits version
pinning (L21) but does not link `(model_id, model_version)` to a
constraint-region version. A FIRM record under stale Heston-2018 may
violate Heston-2024 constraints; the certifier signed off in 2019.

**Remediation.** Add (D-CAL'): $x_{t|t}^{\text{cert}} \in \Theta_{AF}^{m, v_t}$
where $\Theta_{AF}^{m, v_t}$ is the no-arbitrage region for model $m$
under constraint version $v_t$ active at time $t$, and $v_t$ is recorded
in the certification record. Add (E-GATE'): the FSM transition to
`FIRM` checks $v_{\text{record}} = v_{\text{current}}$; otherwise the
record is downgraded to `STALE` until recertified under the current
constraint set. The proposal does not name $v_t$ as a first-class
field on `CertifiedCalibration`. **BLOCKING.**

---

### B6. The 4 "unwitnessed laws" mis-classify witness-able laws as
unwitness-able, and conflate finite-test impossibility with property impossibility.

**Location.** `proposal_v1.md` §9.4 and `phase2/correctness.md` §5
(U1–U4).

**Code.** §9.4 lists L1, L4, L8, L13 as "unwitnessed by any finite test
suite"; the surrogate strategies are accepted modulo Phase 3 ruling.

**Property violated.** Three of the four are mis-classified.

- **U1 (L13 Liveness over unbounded futures).** The genuine
  unwitness-ability is that no finite simulation can verify behaviour
  at $t = \infty$. But this is *not* the load-bearing claim — the
  load-bearing claim is "every registered obligation reaches a terminal
  state by its deadline + bounded compensation horizon". That claim
  *is* witness-able by structural induction on the obligation type
  *combined with* a finite-horizon simulation. The proposal already
  states the inductive surrogate (§5 U1 inductive). Therefore L13 is
  witnessed by the conjunction of two finite witnesses; declaring it
  "unwitnessed" is over-claiming the residual risk. **Re-classify as witness-able.**

- **U2 (L4 Bitemporal under unbounded restatement).** Similarly: the
  load-bearing claim is bounded by the *retention horizon*, which is
  itself a finite policy parameter (L7 / C-A10). The unbounded version
  is mathematically correct but operationally uninteresting. Re-state
  L4 as "bitemporal coherence under chains bounded by retention
  horizon" and witness it directly. **Re-classify as witness-able.**

- **U3 (L1 Lineage under undisclosed sources).** *This is genuinely
  unwitness-able* because the threat model includes a malicious vendor.
  But the proposal's surrogate "trust-assumption registry + threat
  model + multi-source consensus" is **not a witness**; it is a
  *reduction* (the property holds *if* the assumptions hold). The
  proposal does not flag this distinction. (Huet: "A reduction of
  property P to assumption A is a witness of P only when A is itself
  witnessed.") The trust assumption is not witness-able; therefore L1
  itself is not witnessed even via the surrogate. **Severity remains
  unwitnessed; the surrogate is mis-described.**

- **U4 (L8 Replay determinism under cosmic-ray bit flips).** The
  proposal cites "content-addressing + erasure coding +
  cross-replica verification". This *is* a witness — bit flips are
  detected with probability $1 - \epsilon$ for explicitly-bounded
  $\epsilon$. The proposal should state $\epsilon$ as a function of
  storage-integrity primitives. **Re-classify as witness-able with
  explicit failure probability.**

**Remediation.** Restructure §9.4 into:
- *Genuinely unwitnessed* (1 law): U3 (L1 lineage). Explicitly
  acknowledge that the surrogate is a reduction, not a witness, and
  name the C-A holders.
- *Witnessed via composition* (3 laws): U1 (L13), U2 (L4), U4 (L8) —
  each with the composed witness explicitly stated and the residual
  risk parameter (horizon, retention, $\epsilon$) declared as a
  policy variable.

The current §9.4 conflates all four into a single bucket and asks Phase
3 to rule "are surrogates accepted as proxies, or accepted as
architectural risks". The right question is *different per law*; the
proposal does not decompose. **BLOCKING.**

---

### B7. Totality claims for accessor functions reference undefined domains.

**Location.** `phase2/formalis.md` §3 (36 accessor table), summarized in
`proposal_v1.md` §3.

**Code.** Accessor A11 `position_state : (WalletId, UnitId) → Option[PositionState]`,
declared "Genuinely 3-valued: None, Some(zero), Some(nonzero)".
Accessor A22 `apply_all : List[Move] → LedgerState`, declared "Total
under valid prefix; precondition: prefix must satisfy P1–P3".
Accessor A24 `replay : WorkflowHistory → WorkflowState`, declared
"Total under workflow-code determinism; precondition".

**Property violated.** Three accessors marked "Total" depend on
preconditions that are *themselves* the load-bearing properties. (Coquand
on dependent types: "A precondition is part of the type. If your
domain is `{x : T | P(x)}`, you must produce $P$, not assume it.")

- A11: "Some(zero) ≢ None" requires that the storage layer never
  conflates the two. The proposal mandates "the storage layer must
  refuse a delete-row API on PositionState" (§3 critical totality
  discharge). This is a *runtime obligation* on the storage layer
  expressed in prose. There is no type-level guard that prevents a
  storage-layer implementation from violating it. The accessor's
  totality is therefore **conditional on a discipline external to the
  data spec**, and the proposal lists no enforcement mechanism.

- A22: "Total under valid prefix" — but `apply_all`'s very purpose is to
  *establish* what a valid prefix is. The precondition "prefix must
  satisfy P1–P3" is checked by `apply_all` itself; calling it a
  precondition is begging the question. Either `apply_all` is
  partial (`Result<LedgerState, P_violation>`) or the prefix is
  refined into a `ValidPrefix` newtype with a private constructor —
  the proposal picks neither.

- A24: "Total under workflow-code determinism" — same defect as B2.

**Remediation.**
- For A11: introduce a refined type `RowStored<W, U>` with a private
  constructor, only writeable by the `register_or_update` API, never
  by `delete_row`. Declare the storage layer's mutation interface as
  a closed sum of {`Insert`, `Update`, `MarkInactive`} with no `Delete`.
  Then "Some(zero) ≢ None" is type-level.
- For A22: declare `apply_all : ValidPrefix → LedgerState` where
  `ValidPrefix` is the refined image of a successful prefix-check; or
  declare `apply_all : List[Move] → Result<LedgerState, ConsViolation>`.
  Choose one. The proposal does neither.
- For A24: see B2 remediation.

**BLOCKING** because the totality table is the load-bearing claim of
§3 (the FORMALIS test gate "Totality"); three of its top-five
load-bearing entries are marked total under conditions the proposal
does not enforce.

---

## §2 — UNMITIGATED MAJOR findings (M1–M6)

### M1. The 24-leaf taxonomy admits L7 (Policy/Configuration) and L23
(Capability) without specifying their mutation discipline as a closed sum.

**Location.** `proposal_v1.md` §3.1 (L7); §3.6 (L23); §9.2.

**Code.** L7 carries "rounding mode, tolerance thresholds, accounting
classification map, capability schema, version pins". §9.2 reconciles
jane-street V9 (no Policy as load-bearing) with NAZAROV L7 by saying
"L7 is admitted as a thin sidecar (≤30 fields)".

**Issue.** The 30-field cap is a heuristic, not a structural argument.
Three failure modes:
1. The "capability schema" inside L7 is *itself* the schema for L23.
   This couples two leaves that the taxonomy lists as independent —
   a circular reference. (de Moura: "The SMT solver does not accept
   forward references that cycle. Your data spec should not either.")
2. The "tolerance thresholds" are consumed by L13 (CalibratedMarketObject
   certification) and L15 (ValuationRecord quality gate). A bitemporal
   change to L7 thresholds invalidates downstream certifications. The
   proposal asserts L7 is bitemporal/version-pinned but does not state
   the *recertification cascade*.
3. "Version pins" inside L7 are a pointer to L21. L7 and L21 are
   listed as separate leaves but are mutually referential. Either L7
   subsumes L21, or L21 is a projection of L7, or they are duplicate
   leaves.

**Remediation.** Either decompose L7 into three sub-leaves:
- L7a Numeric Policy (rounding, decimals, currency)
- L7b Threshold Policy (tolerances, freshness)
- L7c Reference Schema (capability schema, accounting class map)

with separate mutation disciplines, **or** absorb L7 into L21 entirely
(every L7 datum is a "policy version pin"). The proposal does neither
and the 30-field cap will not survive Phase-4 implementation.

### M2. The bitemporal-mandatory rule (NAZAROV N6) is asserted for
"every leaf in C1 and C4" but L4 (Calendar) is genuinely bitemporally
*incoherent* under retroactive amendment.

**Location.** `proposal_v1.md` §0 anchor 3; §3.1 L4; §9.5.

**Code.** L4 (Calendar/Convention) is admitted as bitemporal-mandatory.
TEMPORAL §9.5 admits "retroactive calendar amendments invalidate
scheduled timers in already-running workflows" as the worst awkward fit.

**Issue.** A retroactive holiday addition for $d_0$ at knowledge time
$t_k > d_0$ creates a *contradiction*: the workflow that scheduled a
payment for $d_0$ at $t < t_k$ has either:
(a) already paid (move emitted, hash-chained, irreversible — and now
incorrect under the amended calendar), or
(b) not yet paid (the timer fires on $d_0$, but $d_0$ is now a
holiday — the next-business-day-adjustment rule must re-resolve the
date, *which depends on the calendar at what knowledge time?*).

The bitemporal axis says: "the calendar at time $t_k$ supersedes the
calendar at $t < t_k$"; the v10.3 referential integrity rule says:
"a workflow consumes the calendar version it cited at registration".
These two rules contradict on retroactive amendment. The proposal's
"workflow versioning + signal-driven schedule rebuild" reconciliation
(§3.1 L4 T-line) is hand-waving — *which version of the calendar* does
the rebuild use?

**Remediation.** State explicitly:
- (R1) The calendar consumed by a settled move is *frozen* at the
  knowledge-time of the cited version; subsequent amendments do not
  retro-correct settled moves.
- (R2) The calendar consumed by an unsettled timer is *resolved* at
  timer-fire time using the latest knowledge; the workflow code must
  re-resolve dates on every `now()` boundary.
- (R3) The amendment handler emits a `CORRECTION` transaction for any
  *already-settled* move that the amendment would have re-routed, with
  explicit acceptor sign-off.

The proposal does not state (R1–R3); it points to TEMPORAL §6 and
moves on. **MAJOR.**

### M3. The 5 "compositional theorems" overlap with the 14 "consistency
laws" in ways that are not reconciled.

**Location.** `proposal_v1.md` §4 (14 laws) vs §8 (5 theorems).

**Issue.** Compositional Theorem 1 (Conservation Lifting) is the
composition of L5 + L6 + L7. Theorem 2 is L8 + L10. Theorem 3 is L13.
Theorem 4 is L1 + L9 + L8. Theorem 5 is L11 + L12. The 5 theorems are
*aggregations* of subsets of the 14 laws. The proposal calls one set
"laws" and the other set "theorems" without stating the relationship.
(Avigad: "Mathematical induction is the foundation of formal
verification. The base of the induction must be axioms; the apex must
be theorems. The middle layer is *neither* — it is lemmas, and they
must be named as such.")

The 14 "laws" are themselves not all axioms (some are derived from
others — L7 follows from L5 by restricting scope; L9 follows from
L8 by restricting to CDM events; L10 is a special case of L8).
The proposal does not state the dependency DAG.

**Remediation.** Produce a *dependency DAG* over the 14 laws and the
5 theorems, naming:
- which laws are independent (axioms);
- which laws are derived (lemmas, with the derivation cited);
- which theorems are *aggregations* (compositions of independent laws);
- which theorems require *additional hypotheses* beyond the laws (e.g.,
  Theorem 2 requires E-WF; Theorem 5 requires E-GATE).

Until this DAG exists, the relationship between "law" and "theorem"
is rhetorical, not structural. **MAJOR.**

### M4. Termination arguments confuse "bounded retry" with
"termination" in workflows that retry indefinitely on transient failure.

**Location.** `phase2/formalis.md` §4 (T1–T30); cited by `proposal_v1.md`
§3.

**Issue.** T3 (reference data ingestion), T5 (LEI ingestion), T10
(raw observation), T25 (activity invocation) are listed as "bounded
retry" with decreasing measure `retries_remaining`. But Temporal's
default activity retry policy is **unbounded retries with exponential
backoff** for `Application` failures classified as retryable. (Coquand
on T30 was correctly invoked: "A smart contract that does not
statically bound its loops is a smart contract that does not
terminate.") The proposal cites Avigad approvingly: "every retry must
reduce a counter; otherwise termination is wishful thinking." The cite
is correct; the implementation is wrong. The proposal does not
mandate `MaximumAttempts` to be set on every activity policy; it
merely says "default 5", which is a Temporal policy default that
**does not apply unless explicitly set**.

**Remediation.** Mandate, as part of the data spec, that every
activity invocation in the orchestration layer carries an explicit
`MaximumAttempts ≥ 1` and `MaximumInterval` set to a finite duration.
Add this as part of L24 OrchestrationState's invariant set. The
proposal does not. **MAJOR.**

### M5. The 26 CDM-missing leaves create a dependency the proposal
declares "strategic" but does not gate.

**Location.** `proposal_v1.md` §7 (5 strategic gaps); §9.3.

**Issue.** Gap #1 (Calibrated Market Data Layer) is asserted to "seed a
`cdm-valuation-lib` upstream proposal". This is a multi-year effort
under the FpML/CDM governance process. The proposal states "Phase 3
must rule on whether the Ledger is willing to operate with CDM-missing
leaves represented as Ledger-internal types" but does not state the
*migration cost* if/when CDM-native types arrive. (Leroy on CompCert:
"Semantic preservation must be proved pass by pass." The proposal asks
us to commit to a Ledger-internal calibration layer and re-prove
Theorem 5 once CDM-native types replace the internal types — without
naming the migration discipline.)

**Remediation.** Add §7.6: "Migration discipline for Ledger-internal
types when CDM equivalents arrive." Specify:
- (M1) Internal type carries a `cdm_native_pending` flag.
- (M2) Migration is a `(internal_id, cdm_id, mapping_version)` record
  in L12 ObligationStore (the migration is itself an obligation with
  deadline = "CDM v$X$.0 release date").
- (M3) Until migration, the bitemporal axis carries the ledger-internal
  axis; after migration, the axis is dual (internal | CDM-native).

The proposal does not state any of this; it treats CDM-missing as a
risk to flag, not a discipline to impose. **MAJOR.**

### M6. The reconciliation between v10.3 StatesHome 3-map and the
24-leaf taxonomy does not preserve the writer-cap structure.

**Location.** `proposal_v1.md` §3.1–§3.3 (L1, L8, L9 → StatesHome maps
1, 2, 3); `phase2/formalis.md` §2 L5.W1, L6.W1 (single-writer per
field via phantom-typed writer capability).

**Issue.** StatesHome C11 says "single-writer per field". The
proposal's L8 and L9 both invoke writer-cap phantom types, but the L1
ProductTerms, which is StatesHome map 1, is **not** subject to a
writer-cap discipline as stated — it is "registration-total"
(`unit-registration` and `terms-amendment` workflows). Yet the
StatesHome 3-map ruling is *canonical* (per user memory) and demands
all three maps share C11. Either:
(a) ProductTerms IS subject to per-field writer cap (and the proposal's
description "owner: unit-registration" is a writer cap, just stated
informally), in which case the formal type-level encoding is missing,
or
(b) ProductTerms is NOT subject to C11 and the 3-map ruling needs
amendment.

(Paulin-Mohring: "Extraction from Coq produces total functions. Your
code should aspire to the same. A type-level encoding stated in prose
extracts to nothing.")

**Remediation.** Decide (a) or (b) and state the decision as part of
the canonical 3-map property. For (a), add a writer-cap signature to
every L1.W and L1.C invariant in `phase2/formalis.md`. The proposal
does neither. **MAJOR.**

---

## §3 — MINOR findings (m1–m5)

### m1. Inductive structure of L14 MoveStream is not explicit.

The MoveStream is described as "append-only hash-chained" but the
inductive principle is not given. Avigad: "Every hash chain admits a
structural induction: $P(\text{genesis}) \land (\forall n.\, P(\Sigma[n]) \implies P(\Sigma[n+1])) \implies (\forall n.\, P(\Sigma[n]))$.
State the induction principle as part of L14's type signature."
**Remediation.** Add an `Inductive_HashChain` type-level statement.

### m2. The "9-shape canonical algebra" of idempotency keys (L20) is
not closed.

`proposal_v1.md` §3.6 lists 9 shapes: "`unit_id`, `tx_id`,
`business_event_id`, `obligation_id`, `signal.idempotency_token`,
`snap_id`, `(unit_id, version_seq)`, `(workflow_id, run_id)`,
`(calibrated_object_id, certification_timestamp, model_id)`". These
are 9 enumerated cases but no closed-sum algebraic specification
ensuring "no 10th shape can be added without amending the spec".
**Remediation.** State `IdempotencyKey = ⊕_{i=1..9} K_i` as a closed
sum.

### m3. The "polymorphism by sum type, not inheritance" principle (P10)
is not enforced for the `Move` ↔ `StateDelta` ↔ `BusinessEvent` triple.

The triple is described in L10 as "sum types" but their relationships
(when do they co-occur in a Transaction? when does a StateDelta
appear without a Move?) are stated only in prose. **Remediation.** Add
a *witness type* for the constraint: `Transaction = (NonEmpty<Move>, [StateDelta], CDMBusinessEvent) | (Empty, NonEmpty<StateDelta>, CDMBusinessEvent)`.

### m4. The "registration totality" property (StatesHome C5) is
referenced in L1 and L8 but not given a single canonical statement.

§3.1 L1 N-line says "registration-total" but the predicate is not
defined in the proposal; it is in the v10.3 spec. Cross-referencing is
fine, but a one-line restatement at the data-spec layer is owed.
**Remediation.** Add §1.3 "Cross-reference glossary" with each
v10.3-derived predicate restated.

### m5. The "convergence" criterion (zero blocking, zero unmitigated
major, no minor without trade-off) is asymmetric.

§10 demands "no minor improvement without trade-off". This is a
trap: minors *should not* require trade-offs (that is what makes them
minor). The criterion as written rejects all minor improvements unless
a downside is named. **Remediation.** Rephrase as "no minor improvement
without explicit accept/reject ruling and rationale".

---

## §4 — Verdict against the FORMALIS Test gates

| Gate | Pass / Fail | Comment |
|---|---|---|
| 1. Specification | **Partial** | 24 leaves named; mutation disciplines partially specified (B1, M1, M6). |
| 2. Types | **Partial** | Refined types catalogued (MINSKY); but accessor preconditions encode runtime obligations as types (B7). |
| 3. Invariants | **Partial** | Per-leaf invariants stated; cross-cutting laws stated; relationship not reconciled (M3). |
| 4. Totality | **Fail** | A11, A22, A24 marked total under preconditions the proposal does not enforce (B7). |
| 5. Determinism | **Fail** | Replay determinism theorem is circular (B2); E-WF cited as both axiom and assumption. |
| 6. Composition | **Fail** | All 5 compositional theorems (B1, B2, B3, B4, B5) have defects in stating the proof obligation. |

**Three of six gates fail; two are partial; one (Specification) is
partial only because the mutation discipline of L7 / L23 is fluid.**

---

## §5 — Grade

**Grade: C+.**

Justification:
- The taxonomy itself is good (24 leaves, 6 classes, 3 sheaves
  decomposition is clean). This earns a B-range floor.
- The proof obligations are *named*, which is rare and worth credit.
- But the *theorems* are not theorems; they are *aspirations*. (Huet:
  "Higher-order unification lies at the heart of mechanizing
  mathematics. A theorem with a hypothesis that contains the
  conclusion is not unifying anything; it is restating.") This pulls
  the grade to C+.
- An A-grade proposal would have:
  (a) the 5 theorems re-stated with non-circular hypotheses;
  (b) a dependency DAG over the 14 laws;
  (c) the 4 unwitnessed laws decomposed into 1 genuinely-unwitnessed
      and 3 composed-witness laws;
  (d) the mutation discipline of every leaf as a closed sum;
  (e) accessor totality discharged through types, not preconditions.

This proposal achieves none of (a)–(e) cleanly. Grade C+ /
**Reject as written; iterate**.

---

## §6 — Convergence ruling

**Convergence: not yet achievable.**

Required to achieve convergence:
- **Address every BLOCKING finding (B1–B7).** Each is a structural
  defect, not a wording issue.
- **Address every UNMITIGATED MAJOR (M1–M6) or downgrade with
  explicit reasoning.**
- **MINOR findings (m1–m5) may be accepted, deferred, or rejected
  with rationale per the proposal's §10.**

Estimated rounds to convergence given the structural defects in B1–B7:
**three additional rounds minimum**, possibly more if B3 (Theorem 3)
requires populating the (event_class, obligation_kind) → κ table from
SBL / CDM lifecycle work that has not yet been done.

---

— end of FORMALIS Phase 3 Round 1 adversarial review —

> *"A theorem whose hypothesis contains its conclusion is not a theorem.
> A totality whose precondition is not enforced is not totality. A
> witness whose surrogate is itself unwitnessed is not a witness. We
> have found all three."*
> — Xavier Leroy, closing the FORMALIS Phase 3 Round 1 deliberation.
