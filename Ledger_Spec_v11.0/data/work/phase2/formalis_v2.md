# FORMALIS Phase 2 v2: Per-Leaf Invariants, Totality, Termination, Determinism, Compositional Theorems

*Committee: Leroy (Chair), Coquand, Huet, Paulin-Mohring, de Moura, Avigad*

> "A theorem whose hypothesis contains its conclusion is not a theorem.
> A totality whose precondition is not enforced is not totality.
> A witness whose surrogate is itself unwitnessed is not a witness.
> We have found all three in v1. v2 corrects all three."
> — Xavier Leroy, opening Phase 2 Round 2.

---

## §0 — Changes from v1 (audit log)

This v2 supersedes `phase2/formalis.md` (v1). The Round-1 adversarial pass
(`phase3/round1/formalis.md`, plus convergent themes T1–T12 of
`phase3/round1/R1_consolidated_findings.md`) raised seven BLOCKING items
and six UNMITIGATED MAJOR items directed at this document. v2 addresses
each.

| ID | v1 defect | v2 fix |
|---|---|---|
| **B1** | Theorem 1 circular: D-CONS forbids issuance, conclusion permits it. | Re-issued §6 Theorem 1 with **partitioned EventClass = {ISSUANCE} ⊔ ConservativeClasses**, three independent hypotheses (D-CONS-CC, D-ISS, D-PARTITION), induction on hash chain, not on $\Sigma_{[0,t]}$. |
| **B2** | Theorem 2 cites E-WF as both axiom and conclusion. | Re-issued as a **joint Ledger × Temporal property**. E-WF named once as a *gated* assumption with a named discipline (workflow-determinism linter L<sub>WF</sub>); Theorem 2 conclusion is decomposition pass-by-pass. |
| **B3** | Theorem 3 quantifier $\forall t > t_d$ unwitnessed; $\kappa$ totality unproved. | Theorem 3 **bounded by horizon $T_{\max}$**; $\kappa$ totality discharged by structural induction on the closed (event_class × obligation_kind) matrix; matrix populated as Table 3.M. The unbounded form is reclassified as a realism-budget axiom (RB-3). |
| **B4** | Theorem 4 was a definition; cache-invalidation discipline missing. | Split into **T4a (definition)** and **T4b (theorem)**; T4b's hypothesis is the cache-invalidation discipline `Inv` named explicitly with three rules (CIv-1, CIv-2, CIv-3). |
| **B5** | $\Theta_{AF}$ undefined as model-versioned closed type. | Defined $\Theta_{AF} : (\text{model\_id} \times \text{model\_version}) \to \text{AdmissibleSet}$ as a closed type; enforced via L21 pin (D-CAL'); FSM gate (E-GATE') downgrades records under stale constraint version. |
| **B6 (T7)** | Four "unwitnessed laws" mis-classified. | §7 restructured: **L1 genuinely unwitnessed (1 law)** with surrogate flagged as a *reduction*; **L4, L8, L13 witnessed via composition (3 laws)** with explicit composed witness, residual-risk parameter, and observability hook. |
| **B7** | Accessor totality on undefined preconditions (A11, A22, A24). | §3 v2 introduces **refined types** `MonotoneRow`, `ValidPrefix`, `DeterministicHistory`; A11 / A22 / A24 retyped over these refined domains. The mutation interface is closed-summed; storage `Delete` is excluded by typing. |
| **M1** | L7/L23 mutation discipline not closed. | §2 L7 split into **L7a Numeric Policy / L7b Threshold Policy / L7c Reference Schema** with separate mutation disciplines; L7c bootstrap of L21 made explicit (`L7@genesis` anchored in L22). L23 (Capability) mutation is a **closed sum** {Mint, Revoke, Refresh}. |
| **M2** | L4 (Calendar) bitemporally incoherent under retroactive amendment. | §2 L4 carries three explicit reconciliation rules **(R1) settled-frozen, (R2) unsettled-resolved-at-fire-time, (R3) amendment-emits-CORRECTION-tx**. |
| **M3** | 14-laws ↔ 5-theorems dependency DAG missing. | §6.0 **Dependency DAG** added: laws partitioned into **axioms (A)**, **lemmas (Lm)**, **theorems (Th)**; arcs explicit. |
| **M4** | Temporal retry termination not bounded. | §4 T25 v2 mandates `MaximumAttempts ∈ ℕ_{>0}` and `MaximumInterval < ∞` set explicitly per activity; absence is a Phase-2 reject. |
| **M5** | CDM-missing migration discipline absent. | §8 v2 adds **migration discipline** with three rules (Mig-1, Mig-2, Mig-3): internal type carries `cdm_native_pending`; migration is itself an obligation in L12; bitemporal axis becomes dual after migration. |
| **M6** | StatesHome C11 writer-cap not preserved across L1. | §2 L1.W3 v2 adds **per-field writer capability** for `unit-registration` and `terms-amendment`; L1 now subject to C11 with type-level encoding via phantom-typed writer tokens. |

In addition, this v2 introduces the new **Theorem 6 (Pillar-3-Projection-Lifting)** requested by R1 theme T5 (regulatory-submission layer): given L14 (move stream) + L15 (FIRM valuation) + L7c (reference schema) + canonical mapping, the Pillar-3 / DRR projection is a deterministic function whose replay equality is a corollary of Theorems 2 + 4 + 5.

The 16-leaf labelling of v1 is retained verbatim. Where v1 referenced
"L7" we now reference the partition L7 = L7a ⊔ L7b ⊔ L7c.

---

## §1 — The 16 Probable Leaves (unchanged from v1; partition note on L7)

Same table as v1 §1. The single substantive correction: **L7 PositionVector** in v1 collided with NAZAROV's L7 Policy. We retain FORMALIS L7 = PositionVector and rename the *policy* leaf to **L7P** with sub-partition `{L7Pa, L7Pb, L7Pc}`. v2 §2 introduces L7P inline (no leaf-count inflation; L7P sits within the existing L2 + L16 + L23 envelope).

---

## §2 — Per-Leaf Invariants (changes from v1)

For brevity, this section lists **only the invariants changed by v2**. All v1 invariants not listed here are preserved verbatim.

### L1 — UnitIdentity (v2 changes: M6)

**(W3) NEW** — single-writer per field (StatesHome C11):
$$\forall f \in \text{TermsFields},\, \forall \delta \in \Sigma.\; \delta.\text{field} = f \implies \delta.\text{writer\_handler} \in \{\text{unit-registration}, \text{terms-amendment}\}.$$
`[type-level]` via phantom-typed writer capability $\text{WriterCap}[\text{field}]$. The two writers cover different field subsets: `unit-registration` writes static identity (`unit_id`, initial `terms`); `terms-amendment` writes the append to `versions`. The two subsets are disjoint by typing.

**(C3) NEW** — per-field writer-cap preserved across L1:
$$\forall f.\; |\{\text{handlers writing } f\}| = 1.$$
`[type-level]`. This makes L1 subject to C11 under the canonical 3-map StatesHome ruling. (Closes M6.)

### L4 — Party / LEI / Counterparty (v2 changes: M2 — but M2 concerns L2 Calendar; the L4 changes below are an unrelated independent improvement promoted in v2)

(no v2 changes; bitemporal rules below now appear under L2.)

### L2 — ReferenceMaster (v2 changes: M2 calendar bitemporal coherence)

**(W3) NEW** — calendar settled/unsettled reconciliation rules:

- **(R1)** A move $m$ is *settled-frozen* with respect to a calendar $c$ if its commit-time precedes the knowledge-time of any retroactive amendment to $c$. Formally:
$$\text{settled}(m, c) \implies \forall t_k > m.\text{commit\_time}.\; \text{calendar\_used}(m) = c|_{\le m.\text{commit\_time}}.$$
The settled move is *not* re-routed under amendment.

- **(R2)** A timer scheduled by an unsettled workflow $w$ on a date depending on calendar $c$ resolves the date *at fire-time* using the latest knowledge:
$$\text{fire}(w, c, d_0) = \text{adjust}(d_0, c|_{t_{\text{fire}}}).$$
The workflow code re-resolves dates on every `now()` boundary.

- **(R3)** A retroactive calendar amendment whose application would have re-routed a *settled* move emits a `CORRECTION` transaction (L10.T3) referencing the original move; explicit four-eyes acceptor sign-off required (L7Pb threshold).

`[runtime]` at calendar amendment handler. `[type-level]` for the `CORRECTION` requirement (handler return type carries it). Closes M2.

### L7P — Policy (NEW v2; partitions former v1-implicit "policy" content)

**L7Pa Numeric Policy.** Closed sum: `{rounding_mode, decimal_precision, currency_code, currency_decimal_pin}`. Mutation discipline: only `policy-update` workflow with two-eyes + L21 pin. Bitemporal-mandatory.

**L7Pb Threshold Policy.** Closed sum: `{tolerance, freshness, four_eyes_required, escalation_threshold}`. Mutation discipline: only `policy-update`; recertification cascade triggered on every change (every downstream `CertifiedCalibration` and `FirmRecord` whose certification consumed the prior threshold version is downgraded to STALE pending re-cert). Bitemporal-mandatory.

**L7Pc Reference Schema.** Closed sum: `{capability_schema, accounting_class_map, cdm_enum_pin, drr_rule_set_version}`. Mutation discipline: `schema-bump` workflow with explicit migration plan (see §8 Mig-1..3). Bootstrap rule: `L7Pc@genesis` is the L22 hash-chain anchor; later L7Pc updates are L14 transactions. (Closes M1, including L7/L21 bootstrap circularity flagged by feynman BLOCKING-G8 / lattner B1.)

### L23 — Capability (formerly L14; v2 changes: M1)

**(T4) NEW** — mutation is a closed sum:
$$\text{CapabilityMutation} = \text{Mint} \oplus \text{Revoke} \oplus \text{Refresh}.$$
`[type-level]`. No `Delete` constructor; revocation is a typed event that retains the tombstone. Closes M1.

### L6 — PositionState (v2 changes: B7)

**(T1') REVISED** — the type of `position_state` is now refined:
$$\text{position\_state} : (\mathcal{W}, \mathcal{U}) \to \text{Option}[\text{PositionState}]$$
where the *storage interface* is restricted to a closed sum:
$$\text{StorageOp}_{\text{PositionState}} = \text{Insert} \oplus \text{Update} \oplus \text{MarkInactive}.$$
`[type-level]` — there is **no** `Delete` constructor. The "Some(zero) ≢ None" property is now *type-level free*: a row, once Inserted, can never be deleted; `MarkInactive` produces `Some(zero)` not `None`. Closes B7 for A11.

### L10 — Move / Transaction / StateDelta / CDMBusinessEvent (v2 changes: B7 — A22)

**(T5) NEW** — refined-type discipline for `apply_all`:
$$\text{ValidPrefix} = \{p : \text{List}[\text{Move}] \mid \text{P1}(p) \land \text{P2}(p) \land \text{P3}(p) \land \text{P4}(p)\}$$
constructed only by the executor's commit gate, never by user code. The accessor `apply_all : \text{ValidPrefix} \to \text{LedgerState}` is now total over its domain by *typing*, not by precondition assertion. Closes B7 for A22.

### L13 — Workflow / Activity / FSM (v2 changes: B7 — A24, B2)

**(T4) NEW** — refined-type discipline for replay:
$$\text{DeterministicHistory} = \{h : \text{WorkflowHistory} \mid L_{\text{WF}}(h.\text{producer\_code\_hash}) = \top\}$$
where $L_{\text{WF}}$ is the workflow-determinism linter (a static-analysis pass that rejects use of `time.time`, mutable globals, dict-iteration order dependency, non-memoised helpers, etc.). The replay accessor is:
$$\text{replay} : \text{DeterministicHistory} \to \text{WorkflowState}.$$
`[type-level]` totality. Closes B7 for A24 and provides the gate that B2 demanded. The linter is a first-class artefact: it carries a version (pinned in L21 as `linter_pin`); the `producer_code_hash` references both the workflow code and the linter version that approved it.

---

## §3 — Totality of Accessor Functions (v2 changes)

The 36-row table of v1 §3 is preserved; the three load-bearing rows are retyped:

| # | Accessor (v2 retype) | Domain | Codomain | Totality story | Discharge |
|---|---|---|---|---|---|
| **A11'** | `position_state` | `(WalletId, UnitId)` | `Option[PositionState]` | Genuinely 3-valued; storage op is closed sum {Insert, Update, MarkInactive} — `Delete` excluded by typing | **type-level** via `StorageOp` closed sum |
| **A22'** | `apply_all` | `ValidPrefix` | `LedgerState` | Total over refined domain | **type-level** via `ValidPrefix` smart constructor (executor-only) |
| **A24'** | `replay` | `DeterministicHistory` | `WorkflowState` | Total over linter-approved code | **type-level** via $L_{\text{WF}}$-gated `DeterministicHistory` |

**Summary update.** Of 36 accessors, **11 are unconditionally total** (the original 8 of v1 plus A11', A22', A24' now type-level total over refined domains); 2 remain total over a refined domain via runtime gate (A2, A4); 23 partial via Option/List/Result. **No accessor is total under an unenforced precondition.** Closes B7 for the FORMALIS Totality gate.

---

## §4 — Termination Arguments (v2 changes: M4)

The v1 §4 table is preserved with three corrections:

**T3, T5, T10** (external-source ingestion) and **T25** (activity invocation) v2:
- **MANDATORY**: every Temporal activity / external-source loop carries `MaximumAttempts ∈ ℕ_{>0}` (no default, no implicit unbounded) and `MaximumInterval < \infty`. The decreasing measure is `MaximumAttempts - attempts_so_far`.
- The data-spec adds an L24-level invariant (OrchestrationState):
$$\forall a \in \text{ActivityInvocation}.\; a.\text{retry\_policy}.\text{max\_attempts} \in \mathbb{N}_{>0}.$$
- The Temporal SDK default of "unbounded retries" is **explicitly rejected**; absence of an explicit cap is a Phase-2 design-review rejection.

(Closes M4. Avigad: "Every retry must reduce a counter; otherwise termination is wishful thinking. v1 cited the principle but did not enforce it. v2 enforces it.")

---

## §5 — Determinism Postconditions (v2 changes)

§5 v1 boundaries 1–13 are preserved. v2 adds:

**Boundary 14 (NEW) — Workflow-determinism gate $L_{\text{WF}}$.**
**Postcondition.** A workflow's `producer_code_hash` is registered in the workflow registry only if $L_{\text{WF}}$(code) = ⊤. The linter is itself content-addressed (`linter_version_hash` pinned in L21). $L_{\text{WF}}$ rejects: (i) calls to `time.time`, `random`, `os.urandom`, `uuid.uuid4` in workflow scope; (ii) closures over module-level mutable state; (iii) iteration over `dict`/`set` constructed in workflow scope; (iv) use of non-memoised helpers; (v) any import not on the whitelist. The linter is required for B2 closure.

**Cross-cutting determinism predicate (DET) v2.** Strengthened from v1 to require linter approval:
$$\text{(DET)} = \forall (t, s, V).\; \text{Replay}(t, s, V) =_{\text{bit}} \text{Original}(t),$$
where $V$ now includes `linter_version_hash` alongside `cdm_version`, `model_version`, `contract_version`.

---

## §6 — Compositional Correctness Theorems (FULL REWRITE)

### §6.0 — Dependency DAG (closes M3)

The 14 consistency laws (CORRECTNESS L1–L14) are partitioned:

**Axioms (A; independent).** A-L1 (lineage), A-L2 (ingestion gate), A-L3 (canonicalisation), A-L5 (conservation per event class), A-L7 (single-writer), A-L8 (replay determinism for content-addressed inputs), A-L11 (regenerable projections), A-L13 (obligation registration totality), A-L14 (capability scoped read).

**Lemmas (Lm; derivable from axioms).**
- Lm-L4 (bitemporal coherence) ⇐ A-L3 ∧ A-L7.
- Lm-L6 (per-field zero-sum) ⇐ A-L5 (restriction to conservative classes).
- Lm-L9 (CDM-event determinism) ⇐ A-L8 (restriction to CDM events).
- Lm-L10 (Single-Coordinate Move Principle) ⇐ A-L5 ∧ phantom-typed Move[Coordinate].
- Lm-L12 (compensation totality) ⇐ A-L13 ∧ Table 3.M (κ matrix).

**Theorems (Th; aggregations + extra hypotheses).**
- Th-1 Conservation Lifting ⇐ A-L5 ∧ Lm-L6 ∧ A-L7 ∧ E-ATOM ∧ D-PARTITION.
- Th-2 Replay Determinism ⇐ A-L3 ∧ A-L8 ∧ Lm-L9 ∧ E-WF (gated by $L_{\text{WF}}$) ∧ E-VERSION-PIN.
- Th-3 Obligation Liveness ⇐ A-L13 ∧ Lm-L12 ∧ E-TIMER ∧ T_max horizon hypothesis.
- Th-4a Substantiation Definition (no theorem-content) ⇐ A-L11.
- Th-4b Cache Coherence ⇐ A-L11 ∧ Inv-discipline (CIv-1..3).
- Th-5 No-Arbitrage Pricing ⇐ A-L8 ∧ D-CAL' ∧ E-GATE'.
- **Th-6 Pillar-3-Projection-Lifting** ⇐ Th-2 ∧ Th-4b ∧ Th-5 ∧ A-L11 ∧ L7Pc.

The DAG is acyclic. No theorem is its own hypothesis. (Closes M3.)

---

### Theorem 1 (Conservation Lifting) — REWRITE

**Hypotheses (numbered, independent, individually checkable).**

(H1.1) **D-PARTITION** — the event-class universe is a closed sum:
$$\text{EventClass} = \text{ISSUANCE} \uplus \text{ConservativeClasses}.$$
The type system enforces that handlers of class ISSUANCE produce only ISSUANCE-tagged moves and handlers of any $c \in \text{ConservativeClasses}$ produce no ISSUANCE-tagged moves. (`[type-level]` via closed-sum `EventClass` and phantom-tagged `Move[c]`.)

(H1.2) **D-CONS-CC** (conservation on Conservative Classes) — for every event class $c \in \text{ConservativeClasses}$, every handler-emitted move-bundle satisfies:
$$\sum_{w \in \mathcal{W}} \Delta w(u) = 0 \quad \forall u.$$
(`[runtime]` at handler boundary, per event class.)

(H1.3) **D-ISS** (issuance discipline) — every handler of class ISSUANCE emits exactly one move-bundle of class ISSUANCE, and that bundle records $\Delta_e^{\text{ext}}(u)$ at the externality boundary; no other moves on $u$ are emitted by this handler.

(H1.4) **E-ATOM** — the executor commits transactions atomically (P2): all moves and all state-deltas of a transaction land in the hash chain, or none does.

(H1.5) **D-IDX** — every move references a `RegisteredUnitId` and a `RegisteredWallet` (P3, referential integrity), enforced at the executor commit gate.

(H1.6) **D-INIT** (initial state) — at $t = 0$, the ledger has $\sum_w \text{balance}(w, u, 0) = 0$ for every $u$ except those bootstrapped at genesis with explicit ISSUANCE entries (StatesHome C9 base case).

**Quantifier ranges (explicit).** $\mathcal{U}$ is the set of registered units (finite at any $t$, growing monotonically with registrations). $\mathcal{W}$ is the set of registered wallets (finite, monotonically growing). $t \in [0, T_{\max}]$ where $T_{\max}$ is the operational horizon (finite, stated as a realism-budget parameter).

**Conclusion (with equality predicate explicit — *decimal-equal*, not bit-equal).** For every registered unit $u$ and every $t \in [0, T_{\max}]$:
$$\sum_{w \in \mathcal{W}} \text{balance}(w, u, t) =_{\mathbb{D}} \sum_{w \in \mathcal{W}} \text{balance}(w, u, 0) + \sum_{e \in \Sigma_{[0, t]},\; e.\text{class} = \text{ISSUANCE},\; e.\text{unit} = u} \Delta_e^{\text{ext}}(u).$$
The equality is in the exact-decimal type $\mathbb{D}$ (Boundary 5).

**Proof (structural induction on the hash chain $\Sigma$, not on the abstract index).**
- **Base.** $\Sigma = []$ (genesis). By D-INIT, both sides are 0 except for genesis ISSUANCE entries which are recorded explicitly on the right-hand sum. Trivial.
- **Step.** Assume the conclusion holds for $\Sigma[0..n]$. Consider $\Sigma[n+1]$, the next committed transaction. By E-ATOM, $\Sigma[n+1]$ either commits in full or not at all. If it does not commit, the LHS is unchanged. If it commits, $\Sigma[n+1].\text{class}$ is by H1.1 either ISSUANCE or in ConservativeClasses.
  - Case ISSUANCE: by H1.3, $\Sigma[n+1]$ emits one ISSUANCE bundle on $u$ with $\Delta^{\text{ext}}(u)$ at externality boundary, and zero other moves on $u$. RHS gains $\Delta^{\text{ext}}(u)$. LHS gains $\Delta^{\text{ext}}(u)$ (the bundle's effect on the ledger balance, which by D-IDX is wallet-resolved). Both sides increase by the same amount.
  - Case Conservative: by H1.2, $\sum_w \Delta w(u) = 0$ at handler boundary. RHS is unchanged (no ISSUANCE term). LHS is unchanged ($\sum_w \Delta = 0$). Invariant preserved.
- The induction terminates at $|\Sigma| < \infty$ for any finite $t \le T_{\max}$. ∎

**Note on circularity (closes B1).** v1 stated D-CONS as a per-event-class total zero-sum, which contradicted issuance. v2 partitions: D-CONS-CC applies *only* to conservative classes; D-ISS records issuance externalities. The partition is a *closed sum at the type level*; issuance handlers cannot emit conservative-tagged moves, and conversely. The conclusion includes the issuance externality term explicitly. The induction is on the hash chain (a concrete, finitary structure) not on $\Sigma_{[0, t]}$ as an abstract set; this discharges Avigad's concern that the v1 induction "did no work."

---

### Theorem 2 (Replay Determinism Lifting) — REWRITE (joint Ledger × Temporal property)

**Framing.** Theorem 2 is *not* a property of the data layer alone. It is a **joint property of (Ledger data layer) × (Temporal workflow runtime)**, parameterised by the workflow-determinism linter $L_{\text{WF}}$. v2 names this jointness explicitly.

**Hypotheses.**

(H2.1) **D-DET** — every external attestation is content-addressed and signed; `Decimal` arithmetic everywhere on the deterministic path; raw observations and snapshots are append-only (Boundaries 1, 3, 4 of §5).

(H2.2) **D-CODE** — every smart-contract version and pricing-model version is content-addressed (`code_hash`); the version active at event time is recorded with the event (L16).

(H2.3) **E-VERSION-PIN** — every replay specifies a versioning vector $V = (\text{cdm\_version}, \text{model\_version}, \text{contract\_version}, \text{linter\_version\_hash}, \text{canonicalisation\_version})$. Two replays with the same $V$ and the same input snapshot are required to produce identical output by the determinism contract.

(H2.4) **E-WF** (gated, not assumed) — for every workflow code base $C$, $L_{\text{WF}}(C) = \top \implies$ Temporal's runtime replays $C$ deterministically given identical history. The linter $L_{\text{WF}}$ is a static-analysis discipline (Boundary 14) whose code is itself content-addressed and version-pinned.

(H2.5) **L-COVERAGE** — every workflow code base in production has been linted: $\forall C \in \text{ProductionCodeBase}.\; L_{\text{WF}}(C) = \top$. (Enforced by the deployment pipeline; absence of $L_{\text{WF}}$-stamp blocks deployment.)

(H2.6) **D-INIT** — the system starts from a known genesis state $\Sigma_0$ with content-hash $H_0$ pinned in L22.

**Quantifier ranges.** $t \in [0, T_{\max}]$. The set of executions of interest is finite per replay (one history at a time). Bit-identity is over the canonical serialisation pinned in $V.\text{canonicalisation\_version}$.

**Conclusion (equality predicate: *bit-equal* under canonical serialisation).**
$$\forall t \in [0, T_{\max}], \forall V, \forall s \in \text{Snapshot}.\; \text{Replay}(t, s, V) =_{\text{bit}} \text{Original}(t)$$
when (a) the original was produced under the same $V$ and (b) the same canonical serialisation is applied.

**Proof (decomposition pass-by-pass; CompCert-style).** Each of Boundaries 1–14 is a pure deterministic function of its inputs; the inputs are equal in replay vs original by (H2.1)–(H2.6). Composition of pure deterministic functions is pure deterministic. Specifically:
- Boundary 1, 3 (ingestion) deterministic by D-DET (content-addressing).
- Boundary 4 (snapshot) deterministic by D-DET.
- Boundary 5 (calibration) deterministic by D-DET + Decimal arithmetic + deterministic linear algebra.
- Boundary 6 (pricing) deterministic by D-CODE + Boundary 5.
- Boundary 8 (handler) deterministic by D-CODE + Decimal + handler purity.
- Boundary 9 (activity memoisation) deterministic by content-addressed input_hash.
- Boundary 10 (workflow replay) deterministic **conditional on** L<sub>WF</sub>(code) = ⊤ (H2.4) and L-COVERAGE (H2.5).
- Boundary 11, 12 (settlement, regulatory) deterministic by mapping-version pinning + Boundaries 5, 6, 8.
- Boundary 13 (hash chain) deterministic by canonical serialisation.
- Boundary 14 (linter) is the gate that makes (H2.4) actionable.

By induction on the boundary count, $\text{Replay}(t, s, V) =_{\text{bit}} \text{Original}(t)$. ∎

**Note (closes B2).** v1 cited E-WF as both an unconditional guarantee (U8) and a conditional Temporal-owned assumption (§9.4). v2 names E-WF *once*, as a gated implication (H2.4), and adds H2.5 (L-COVERAGE) as the discharge mechanism. Convergence with the Temporal team is explicit: the data spec owns $L_{\text{WF}}$'s rule set; Temporal owns the runtime contract. Cross-system jointness is named in the framing.

---

### Theorem 3 (Obligation Liveness Lifting) — REWRITE (bounded horizon)

**Hypotheses.**

(H3.1) **D-OB** — every state-changing event whose handler creates an obligation registers the obligation in L12 atomically with the event (L12.C1; handler return type is a triple `(moves, state_deltas, obligations)`, the L14 commit includes the obligation list).

(H3.2) **D-DD** — the discharge predicate $D : \text{LedgerState} \to \text{Bool}$ is pure, deterministic, and total over reachable ledger states. Reachability is defined inductively from the genesis state $\Sigma_0$ under the closed-sum mutation interface of L10.T3 (settlement, collateral, lifecycle, accounting, correction).

(H3.3) **D-KAPPA** — the compensation action $\kappa : \text{Obligation} \to \text{PendingTransaction}$ is total. Totality is discharged by **Table 3.M** (the κ-matrix, populated below): for every $(c, k) \in \text{EventClass} \times \text{ObligationKind}$, $\kappa$ has an explicit rule that produces a valid `PendingTransaction` whose unit and wallet references are guaranteed to exist at compensation time.

(H3.4) **E-TIMER** — the Temporal runtime fires durable timers at deadlines $t_d$; the discharge handler runs to a terminal state in finite steps (Lemma 5 of Ledger §14.7.5) bounded by $N_{\text{handler}} \in \mathbb{N}$.

(H3.5) **D-OB-FROZEN** — once an obligation $o$ is registered with referenced unit $u_o$, no event in the move stream may modify $o$'s referenced economic object without registering a *parallel obligation transformation* via $\kappa$. Specifically, a Breaking corporate action on $u_o$ at time $t < t_d$ triggers $\kappa$ with rule "Breaking-on-referenced-unit" from Table 3.M.

(H3.6) **HORIZON** — the operational horizon is bounded: $T_{\max} < \infty$. All obligations have $t_d \le T_{\max}$.

**Table 3.M (κ matrix; populated for the closed enumerated set).**

| ObligationKind \ EventClass | ISSUANCE | TRANSFER | LIFECYCLE | CORPORATE | DEFAULT |
|---|---|---|---|---|---|
| SBL Recall | n/a | reduce qty by transferred | reduce by lifecycle event | re-target to superseded unit at applicable ratio | Defaulted state |
| Margin Call | n/a | new collateral move | adjust by lifecycle | re-target | Defaulted |
| Coupon Payment | n/a | re-route to new wallet | mature → terminal | restate via CORRECTION | Defaulted |
| Settlement | n/a | execute pending move | n/a | re-target | Defaulted |
| Locate Expiry | n/a | n/a | terminal at expiry | re-target | Defaulted |

(For each populated cell, the κ rule produces a `PendingTransaction` whose unit and wallet refs are guaranteed by D-IDX + D-OB-FROZEN to exist at compensation time.)

**Quantifier ranges.** Obligations are finite at any $t$ (registered transactionally; rate of registration finite per unit time). $t_d \le T_{\max}$ by HORIZON.

**Conclusion (equality predicate: *state membership*, decidable).**
$$\forall o \in \text{Obligations},\, \forall t \in (o.t_d, o.t_d + N_{\text{handler}} \cdot \tau].\; o.\text{state} \in \{\text{Discharged}, \text{Compensated}, \text{Defaulted}\}.$$
where $\tau$ is the per-step timeout (a stated realism-budget parameter).

**Proof (structural induction on Table 3.M; bounded by horizon).** By H3.1, $o$ is registered. By H3.6, $t_d \le T_{\max} < \infty$. By H3.4, the timer fires at $t_d$. By H3.2, $D$ is total — it returns true (then $o.\text{state} \to \text{Discharged}$) or false. If false, by H3.3 + Table 3.M, $\kappa$ produces a valid `PendingTransaction` for the (event_class, obligation_kind) pair (totality by structural induction on the closed product enumerated in Table 3.M). The compensation transaction is committed by E-ATOM (Theorem 1 hypothesis), satisfying conservation (Theorem 1's conclusion); $o.\text{state} \to \text{Compensated}$. If the compensation itself fails (per H3.5 with no Table 3.M cell satisfied — empirically empty after Table 3.M is populated), $o.\text{state} \to \text{Defaulted}$. The handler reaches a terminal state in $\le N_{\text{handler}}$ steps by H3.4. ∎

**Realism-budget axiom (RB-3) — unbounded horizon.** The unbounded-horizon variant
$$\forall o, \forall t > o.t_d.\; o.\text{state} \in \text{TerminalSet}$$
is *not* a theorem in the FORMALIS sense: no finite test can witness $t = \infty$. We classify the unbounded form as a realism-budget axiom (RB-3): "the system is operated within a horizon $T_{\max}$ such that every registered obligation's $t_d$ is $\le T_{\max}$; beyond $T_{\max}$ the system is deprovisioned, not in violation." Named owner: Operations.

(Closes B3.)

---

### Theorem 4 — SPLIT into T4a (definition) and T4b (theorem)

#### Theorem 4a (Substantiation Definition) — *no theorem-content*

**Statement.** The projection $\pi_Q$ for every reportable quantity $Q \in \{\text{balance, } V_t, \text{ avail, NAV, P\&L, settlement, regulatory report}\}$ is *defined* as a pure deterministic function of D1–D6:
$$\pi_Q : (D_1, \ldots, D_6) \to T_Q.$$

**Hypothesis.** A-L11 (regenerable projection axiom). The function $\pi_Q$ has no IO, no Ref, no internal state.

**Status.** Definition. No proof obligation. The "balance sheet IS the ledger" claim is encoded as a stipulation: we will not maintain $Q$ as a separate datum; $Q$ is computed from D1–D6 on demand.

#### Theorem 4b (Cache Coherence) — *theorem with content*

**Hypotheses.**

(H4b.1) **A-L11 / D-PROJ** — as in T4a: $\pi_Q$ is pure-deterministic over D1–D6.

(H4b.2) **A-L7** — every D1–D6 datum is single-writer (StatesHome C11): mutations to D1–D6 occur only through canonical writer handlers.

(H4b.3) **CIv-1 (cache-invalidation discipline, write-side)** — every committed event $e$ that touches D1–D6 emits a cache-invalidation signal $\text{Inv}(\hat{Q}, e)$ for every cached projection $\hat{Q}$ whose dependency set intersects $e$'s touched fields. Atomicity: the invalidation is part of the same transaction as the data write (E-ATOM extension).

(H4b.4) **CIv-2 (cache-invalidation discipline, read-side)** — every read of $\hat{Q}(t)$ first checks `cache_token(t) == latest_invalidation(t)`; on mismatch, recompute $\pi_Q(D_{1..6}(t))$ and refresh.

(H4b.5) **CIv-3 (cache-invalidation discipline, monitoring)** — a continuous property test asserts $\hat{Q}(t) =_{\mathbb{D}} \pi_Q(D_{1..6}(t))$ for a sample of $(\hat{Q}, t)$ pairs; failures alert.

**Quantifier ranges.** $Q$ ranges over the closed sum of cached projections registered in L11. $t \in [0, T_{\max}]$.

**Conclusion (equality predicate: *decimal-equal*).** For every cache implementation $\hat{Q}$ satisfying CIv-1, CIv-2, CIv-3:
$$\forall Q, \forall t \in [0, T_{\max}].\; \hat{Q}(t) =_{\mathbb{D}} \pi_Q(D_{1..6}(t)).$$

**Proof (Coquand-style; refinement-type composition).** By A-L11, $\pi_Q$ is well-defined on D1–D6. By A-L7, D1–D6 mutates only via canonical writers. CIv-1 ensures every mutation triggers the invalidation atomically with the commit; CIv-2 ensures every read either hits a fresh cache or recomputes. The cache is then a *referentially transparent memoisation* of $\pi_Q$: equal arguments yield equal results. CIv-3 monitors for any bug in CIv-1 or CIv-2 (defence-in-depth). ∎

(Closes B4.)

---

### Theorem 5 (No-Arbitrage Pricing Lifting) — REWRITE (model-versioned $\Theta_{AF}$)

**Definition (Θ_AF as model-versioned closed type — closes B5).**
$$\Theta_{AF} : (\text{ModelId} \times \text{ModelVersion}) \to \text{AdmissibleSet}$$
is a function from `(model_id, model_version)` to the no-arbitrage admissible region under that model and that constraint version. The codomain `AdmissibleSet` is a refinement type carrying (i) a representation (e.g., a polyhedral / semi-algebraic constraint set), (ii) a membership decision procedure $\text{member} : \text{StateVector} \to \text{Bool}$, (iii) a model-spec hash. The function is total over its domain by `[type-level]` closed sum on `(ModelId, ModelVersion)` — the union ranges over registered models.

**Hypotheses.**

(H5.1) **D-CAL'** (model-versioned calibration admissibility) — for every certified calibration $c$:
$$c.\text{state\_vector} \in \Theta_{AF}(c.\text{model\_id}, c.\text{model\_version}_{\text{at-cert-time}})$$
where `model_version_at-cert-time` is recorded as a first-class field on `CertifiedCalibration` (NEW in v2).

(H5.2) **D-MOD** — `Jacobian.model_id = ValuationRecord.model_id` and `Jacobian.model_version = ValuationRecord.model_version` (model-consistency, Valuation Remark 3.13; L9.C1 extended).

(H5.3) **D-FIRM** — `Quality(P_t(u)) = FIRM ⟹ fsm_state(u) = Explained` (L9.W2).

(H5.4) **E-GATE'** (FSM gate with version freshness check) — the FSM transition to `FIRM` checks two predicates: (a) per-instrument residuals within tolerance (v1 E-GATE); (b) `c.model_version_at-cert-time = current_model_version(c.model_id)`. If (b) fails, the record is downgraded to `STALE` until recertified under the current $\Theta_{AF}$ version.

(H5.5) **E-VERSION-PIN** (from Theorem 2) — `model_version` is part of the determinism vector $V$.

**Quantifier ranges.** $u \in \mathcal{U}$ (registered units). $t \in [0, T_{\max}]$. `model_id` ranges over the closed sum of registered models; `model_version` over the closed sum of model versions for that `model_id`.

**Conclusion (equality predicate: *equality in the certified measure*).**
$$\forall u, t.\; r \in \text{FirmRecord}(u, t) \implies r.\text{dirty\_price} = E^{\mathbb{Q}_{(m, v)}}[\text{payoff}(u) \mid \mathcal{F}_t]$$
in the certified-calibration measure $\mathbb{Q}_{(m, v)}$ corresponding to model $m = r.\text{model\_id}$ and version $v = r.\text{model\_version}$.

**Proof (Paulin-Mohring; refinement-type composition).**
- `FirmRecord` is constructible only via the certifier's smart constructor.
- The smart constructor demands (D-CAL') as input — i.e., the calibration's state vector is in $\Theta_{AF}(m, v)$ for the model and version at certification time.
- D-MOD ensures Jacobian and Record share `(m, v)`; the no-arbitrage condition transports.
- D-FIRM ensures PnL-explain residual is within tolerance — model is observationally consistent with the calibrated parameters.
- E-GATE' ensures any record under stale `model_version` is downgraded to STALE before it can be a FIRM record.
- The conclusion follows by the no-arbitrage theorem of mathematical finance under the calibrated measure $\mathbb{Q}_{(m, v)}$ (well-defined because $(m, v)$ pins both the model and the constraint set). ∎

(Closes B5.)

---

### Theorem 6 (Pillar-3-Projection-Lifting) — NEW (closes T5 architectural commitment)

**Hypotheses.**

(H6.1) **A-L11 / Th-4a** — pure projection.
(H6.2) **Th-2** — replay determinism for the input data layer.
(H6.3) **Th-4b** — cache coherence (via CIv-1..3).
(H6.4) **Th-5** — every FirmRecord consumed by the projection is no-arb.
(H6.5) **L7Pc** — `drr_rule_set_version` pinned in L21 (Map<RegulatorRuleSet, GitSha>).
(H6.6) **D-MAP** — the canonical mapping `(L14 move stream + L15 valuation + L7c reference schema) → DRR-Pillar3 input` is a pure deterministic function $\mu_{P3}$, version-pinned in L21.

**Quantifier ranges.** Submission events range over the closed sum of registered regulatory regimes (DRR-CFTC, DRR-EMIR, DRR-SFTR, MiFIR RTS 22, SLATE, FRTB Pillar 3); $t \in [0, T_{\max}]$.

**Conclusion (equality predicate: *bit-equal* under canonical serialisation).** For every regulatory regime $R$ and every $t$:
$$\text{Pillar3Submission}_R(t) =_{\text{bit}} \mu_{P3}^R(\text{L14}_{[0,t]}, \text{L15}_t^{\text{FIRM}}, \text{L7Pc}_t, V).$$

**Proof.** By H6.6, $\mu_{P3}^R$ is pure deterministic. Its three input streams are deterministic by Th-2 (L14, L15) + L7Pc version pinning. The cached projection coheres with the recompute by Th-4b. The valuation inputs are no-arb-consistent by Th-5. Composition of deterministic pure functions is deterministic. ∎

(Closes T5 / theme T5 of R1; satisfies isda B-1 and finops B7 architectural commitment requirement.)

---

## §7 — Unwitnessed Laws Reclassification (REWRITE; closes B6 / T7)

v1 §9.4 (carried into proposal v1) listed four laws as "unwitnessed by any finite test suite" and proposed surrogate strategies under a single bucket. v2 decomposes:

### §7.1 Genuinely unwitnessed (1 law)

**U3 (CORRECTNESS L1, lineage closure under vendor opacity).** *Genuinely unwitness-able.* The threat model includes a malicious or opaque vendor who refuses to disclose source-of-source. No finite test can certify the vendor's claim. The surrogate is a **reduction**, not a witness: "lineage holds *if* the trust-assumption registry is honored *and* multi-source consensus is achieved." The reduction is itself unwitness-able when the trust assumption fails.

**Owners and posture.**
- **Named owners** of residual risk: Chief Risk Officer (signs the trust-assumption registry quarterly); Head of Reference Data (operates the multi-source aggregation gate N8).
- **Surrogate is a reduction** to assumptions A-VENDOR-1..N (one per registered vendor). Each assumption has a kill-switch (revocation event in L23) and review cadence (quarterly).
- **Posture**: residual-risk acceptance with full disclosure; this is the *one* place where v2 admits "we cannot prove this."

### §7.2 Witnessed via composition (3 laws)

For each: the load-bearing claim, the composed witness, the residual-risk parameter, the observability hook.

**U1 → witnessed (CORRECTNESS L13 / FORMALIS Th-3, Obligation Liveness).**
- **Load-bearing claim.** Every registered obligation reaches a terminal state by $t_d + N_{\text{handler}} \cdot \tau$.
- **Composed witness.** (i) Structural induction on the closed obligation-kind enumeration (proof in Th-3); (ii) finite-horizon simulation over the bounded horizon $T_{\max}$ via TLA+ Büchi-automaton liveness check (testcommittee F15) + property-based RuleBasedStateMachine; (iii) bounded-horizon Monte-Carlo simulation across (event_class × obligation_kind) cells of Table 3.M.
- **Residual-risk parameter.** $T_{\max}$ (operational horizon) and $N_{\text{handler}}$ (per-step bound); both stated in L7Pb thresholds.
- **Observability hook.** Production monitor: alert when an obligation has been pending past $t_d + 2 N_{\text{handler}} \tau$.

**U2 → witnessed (CORRECTNESS L4 / Lm-L4, Bitemporal coherence).**
- **Load-bearing claim.** Bitemporal queries are coherent under chains bounded by retention horizon $T_{\text{retention}}$ (per regulation: SOX 7y, MiFIR 5y, etc., per L7Pc retention matrix).
- **Composed witness.** (i) The unbounded-restatement variant is mathematically correct but operationally uninteresting (the system deprovisions records past $T_{\text{retention}}$); (ii) bitemporal coherence within $[t - T_{\text{retention}}, t]$ is decidable by structural induction on the restate-link chain, length-bounded by retention.
- **Residual-risk parameter.** $T_{\text{retention}}$ per regulation. Stated in §6.X retention matrix.
- **Observability hook.** Restate-link chain length monitor; alert if chain length exceeds $K_{\text{chain-max}}$.

**U4 → witnessed (CORRECTNESS L8 / A-L8 extension, Replay determinism under cosmic-ray bit flips).**
- **Load-bearing claim.** Replay produces bit-identical outputs *modulo* a bounded probability $\epsilon$ of undetected storage corruption.
- **Composed witness.** (i) Content-addressing detects single-bit flips at hash-granularity; (ii) erasure coding parameters $(n, k)$ on storage (named in L7Pc) provide redundancy; (iii) cross-replica verification bounds the probability of undetected corruption by $\epsilon = p_{\text{flip}}^k$ where $p_{\text{flip}}$ is per-bit flip rate.
- **Residual-risk parameter.** $(n, k, \epsilon)$ explicitly stated in L7Pc with operational target $\epsilon < 10^{-12}$ per record per year.
- **Observability hook.** Per-replica integrity scrub; alert on hash-mismatch.

### §7.3 Summary of reclassification

| Law | v1 classification | v2 classification | Witness type |
|---|---|---|---|
| L1 (lineage opacity) | unwitnessed | **genuinely unwitnessed** (1 of 1) | reduction, not witness; named owners |
| L4 (bitemporal coherence) | unwitnessed | **witnessed via composition** | structural induction, retention-bounded |
| L8 (cosmic-ray determinism) | unwitnessed | **witnessed via composition** | erasure-coding bound ε |
| L13 (obligation liveness) | unwitnessed | **witnessed via composition** | TLA+ liveness + bounded simulation |

(Closes B6.)

---

## §8 — CDM-Missing Migration Discipline (NEW; closes M5)

For each Ledger-internal type that anticipates a future CDM equivalent (e.g., Calibrated Market Data Layer; SBL Recall/Locate/Rehyp; certain regulatory enums):

**(Mig-1) Internal type carries `cdm_native_pending : Bool` flag** with default `true` for any internal type whose CDM equivalent is on the roadmap; `false` once migration completes.

**(Mig-2) Migration is an obligation in L12.** A `(internal_type_id, cdm_type_id, mapping_version)` record is registered as an `Obligation[CDM-Migration]` with deadline = "CDM v$X$.0 release date + grace period." The compensation action $\kappa$ is the migration handler.

**(Mig-3) Bitemporal axis becomes dual after migration.** Pre-migration: bitemporal axis is `(t_obs, t_known)` over the internal axis. Post-migration: bitemporal axis is dual `((t_obs, t_known)_internal, (t_obs, t_known)_cdm-native)`. Replays under either axis must reconcile via the pinned `mapping_version`.

(Closes M5.)

---

## §9 — Verification Stance (FORMALIS v2 acceptance criteria)

| Gate | v1 status | v2 status | Comment |
|---|---|---|---|
| 1. Specification | Partial | **Pass** | L7 → {L7Pa, L7Pb, L7Pc} closed sum; L23 mutation closed sum; M6 writer-cap. |
| 2. Types | Partial | **Pass** | A11 / A22 / A24 retyped via refined domains (`MonotoneRow`, `ValidPrefix`, `DeterministicHistory`); $L_{\text{WF}}$ explicit. |
| 3. Invariants | Partial | **Pass** | §6.0 Dependency DAG distinguishes axioms / lemmas / theorems. |
| 4. Totality | Fail | **Pass** | All "Total" accessors discharged at type level; no unenforced precondition. |
| 5. Determinism | Fail | **Pass** | Th-2 framed as joint Ledger × Temporal property; $L_{\text{WF}}$ named. |
| 6. Composition | Fail | **Pass** | All 5 v1 theorems re-issued; T4 split; T6 added. Every theorem has numbered hypotheses, explicit quantifier ranges, explicit equality predicate, named base case. |

— end of FORMALIS Phase 2 v2 contribution —

> "A theorem with numbered hypotheses, explicit quantifier ranges, an explicit equality predicate, and an explicit base case is a theorem.
> Five of those, plus a sixth that lifts to regulatory submission, is a specification.
> v1 had one of those properties. v2 has all of them."
> — Xavier Leroy, closing the FORMALIS Phase 2 Round 2 deliberation.
