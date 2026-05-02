# FORMALIS — Phase 2 Settlement-Team Section: Invariants, Totality, Termination, Proof Obligations, Honest Gaps

**Author**: FORMALIS committee (Leroy chair; Coquand, Huet, Paulin-Mohring, de Moura, Avigad)
**Phase**: 2 (Settlement Team — synthesis)
**Role on the Settlement Team**: own the invariant register, the totality arguments, the liveness theorem, the replay theorem, the type-vs-runtime decomposition, the cardinality estimate, the honest gap list, the counter-examples, the proof obligations imposed on the rest of the team, and the formal-grounds rejections.
**Mainstream convergence baseline (Phase 1)**: virtual wallets + L_15 SettlementObligation + transaction-level settlement-status FSM. Mandatory invariant: economic-exposure-at-T.

This document is normative for the rest of the Settlement Team. Every proof obligation it states must be discharged by the named author before the deferred-settlement specification is considered sound. Every gap it names is honest: it is something the framework cannot discharge without further constraints, and the constraint is named explicitly.

---

## 0. Position relative to Phase 1

Twenty independent Phase 1 proposals were read in full. The convergence is striking and load-bearing:

1. **Trade-date economic recognition is non-negotiable.** Every proposal that attempted otherwise (or appeared to) was rejected by its own author on closer inspection. PnL and risk read `own` only; settlement status is a status overlay, not a quantity overlay.
2. **The open obligation is a first-class typed object.** Whether realised as a unit (`u_so` in halmos / cartan / noether), an L_15 row (formalis Phase 1, jane_street, lattner, geohot, isda, matthias, grothendieck, temporal), a wallet balance (karpathy, finops, feynman, sbl), or a positional sub-coordinate (sbl, feynman), every proposal makes the obligation explicit, addressable, and reconcilable.
3. **Settlement at T+2⁺ is move-less on real wallets.** The economic position was correct from T; settlement is a custody/witness event, not an economic event. (The minority view — feynman/sbl — adds new coordinates and emits virtual-to-virtual rotations at T+2; even there the *real* position never moves.)
4. **Reconciliation is lead-lag by design, not a break.** The identity `ledger_position = depot + InFlight` (or one of its equivalents) is algebraic, not heuristic.

The Phase 1 proposals diverge on six points, each of which we treat as a design choice the Settlement Team must make and we hold the formal cost of:

- **Where the obligation lives**: L_15 row vs unit (`u_so`) vs wallet coordinate. Cost: type-vs-runtime trade-off (§5).
- **Whether to add coordinates**: 7th coordinate (sbl, feynman) vs status overlay (jane_street, geohot, formalis, lattner, halmos, cartan). Cost: bookkeeping cost in §5.
- **Whether to introduce per-trade pending wallets**: per-counterparty (karpathy, finops, ashworth, isda) vs per-instruction (sbl, temporal, lattner) vs none (geohot, jane_street, formalis). Cost: cardinality of the recon identity (§4).
- **Whether settlement events emit moves at all**: no moves (formalis, geohot, jane_street, halmos) vs virtual-to-virtual rotation (karpathy, ashworth, isda, matthias) vs deferred-claim redemption (noether, halmos, cartan). Cost: the form of P26 / DS3 (§3).
- **Whether the FSM lives on the transaction or on the obligation**: transaction (geohot, isda implicit) vs obligation (jane_street, lattner, cartan). Cost: composability of partial fills (§3, §6).
- **Whether to cap obligation tree depth**: jane_street caps at 2; sbl/karpathy/temporal allow recursion. Cost: termination argument (§3).

The invariant register below is **independent of these design choices**. Each invariant is stated in a form that is true for any of the architectural variants — so that the choice between them does not make any invariant unprovable. Where a choice is forced (e.g., Herstatt requires per-leg obligations), we say so.

---

## 1. The canonical invariant register: DS1–DS18

We use the prefix `DS` (deferred settlement) and number from 1. Where an invariant is a specialisation or lift of an existing v10.3 invariant (P1–P10), §13 invariant (P11–P20), or §13/data-spec invariant (P21–P23), we name the parent. Where an invariant is a specialisation of a `Λ` cross-layer law from `ledger_data_v1.0`, we name it. The DS-numbering is reserved for the deferred-settlement extension and does not collide with v10.3 numbering.

For each invariant: (a) formal statement with full quantification, (b) parent invariant if any, (c) compile-time vs runtime classification, (d) severity if violated.

### DS1 (MANDATORY) — Economic-Exposure-at-T

> **For every settlement-typed transaction $\tau$ committed at time $T$ with intended settlement date $t_d \ge T$, for every party wallet $w$ to $\tau$ in any real wallet sector, for every unit $u$ moved by $\tau$, for every $t \in [T, t_d^+] \cup [t_d^+, \infty)$:**
> $$
> w_t(u)[\text{own}] - w_{T^-}(u)[\text{own}] = \sum_{m \in \tau,\,m.\text{unit}=u,\,w \in \{m.\text{src}, m.\text{dst}\}} \text{signed-delta}(m, w)
> $$
> equivalently: there exists no projection $\Pi$ over the move stream + status overlay + obligation log whose value during $[T, t_d^-]$ differs from its value after $\tau$ has reached `Settled` status, holding the price function constant.

**Parent**: v10.3 P1 (conservation), v10.3 §11.4 ("settlement timing distinctions"), v10.3 P10 (PnL path-independence).

**Classification**: hybrid. The forward direction (own moves at T) is compile-time enforceable by capability-typing on `own` write-handlers (see §5; per cartan/minsky/jane_street's C11 discipline). The negative direction (no later projection differs) is runtime, discharged by property-based test + the absence of any write to `own` from a settlement-status handler.

**Severity if violated**: CRITICAL. PnL is wrong, risk is wrong, regulatory capital is wrong. This is the single most load-bearing invariant of the entire deferred-settlement extension; it is the reason the work exists.

**Adversarial test (mandatory)**: perturb `lifecycle_stage` on a subset of obligations; recompute PnL; assert PnL is byte-identical to the unperturbed run. (testcommittee P_DS_1 oracle, formalis Phase 1 §3 DS1, correctness P-PnLSep, jane_street I-1, halmos Invariant 3.1.)

### DS2 — Open-Window Conservation (StatesHome C2 lifted)

> **For every unit $u$ (native or obligation-typed) and every time $t$ (including every $t \in [T, t_d^-]$ during the open window):**
> $$
> Q(u)(t) = \sum_{w \in \mathcal{W}_{\text{real}} \cup \mathcal{W}_{\text{virtual}}} w_t(u)[\text{own}] = 0
> $$

**Parent**: v10.3 P1 (conservation), StatesHome C2 (per-event-class structural zero-sum is total over `EventClass`), Conservation Lifting Theorem (`ledger_data_v1.0` §6.1, cartan §5.3).

**Classification**: runtime, discharged per-handler by the event-class structural argument (StatesHome C2). For variants that introduce new units (deferred-claim units in noether/halmos/cartan, obligation units in matthias) or new coordinates (sbl, feynman), the proof extends by inspection — each issuance and discharge handler is a paired-source/destination write, hence zero-sum.

**Severity if violated**: CRITICAL. Quantities are not conserved; the audit chain is broken.

### DS3 — Reconciliation Lead-Lag Identity (algebraic)

> **For every real wallet $w$ and every unit $u$ and every time $t$:**
> $$
> w_t(u)[\text{own}] = \text{depot}_w^{\text{custodian}}(u, t) + \text{InFlight}_w(u, t)
> $$
> **where**
> $$
> \text{InFlight}_w(u, t) = \sum_{\substack{\tau\,:\,w\in\text{parties}(\tau) \\ \text{SettlStatus}(\tau)\in\{\textsc{Executed,Instructed,Failed,PartiallySettled}\}}} \text{signed-qty}(\tau, w, u)
> $$

**Parent**: v10.3 §13 line 3538 (SBL recon identity); generalisation to non-SBL trades.

**Classification**: runtime, discharged by property-based test. The identity is the *definition* of the reconciliation surface; a violation means either the obligation log mis-tracks an open trade (specification bug) or a confirmation has been recorded without updating obligation state (handler bug).

**Severity if violated**: HIGH. Reconciliation breaks become opaque; operations cannot distinguish lag from genuine break.

**Discharged form alternatives** (formal equivalence): finops E6 (`nostro_external = own - PS_payable + PS_receivable + inflight`), karpathy I-ds-4 (`own = depot + inflight`), sbl P29 (`own + borr - net_outgoing_inflight = depot`), matthias R1, isda E3, temporal I-DS-5, jane_street I-5, lattner P26. **All seven authors converge on the same algebraic identity modulo sign convention.** The Settlement Team must pin the sign convention (§9 PO-3).

### DS4 — No Discharge Without Witness (attestation-driven)

> **For every settlement obligation $o$:**
> $$
> o.\text{state} \in \{\textsc{Discharged}, \textsc{PartiallyDischarged}, \textsc{Compensated}\} \;\Rightarrow\; o.\text{discharge\_witness} \ne \varnothing \wedge \text{verify\_envelope}(o.\text{discharge\_witness}) = \text{true}
> $$

**Parent**: nazarov INV-DS-2 (the strongest form), formalis Phase 1 DS5 caveat, finops E5 (CSDR-attribution determinism), data-spec L_11 ExternalConfirmation contract.

**Classification**: runtime, with a compile-time aid — the FSM transition function is a type-level total function from `(state, witness)` to `state'`, and the no-witness case is encoded as `Reject` (minsky §3.7, cartan §3.2). The cryptographic-signature verification is runtime.

**Severity if violated**: CRITICAL. Allows operators or schedulers to silently mark obligations discharged; equivalent to forging settlement.

### DS5 — Replay Determinism on Out-of-Order Finality

> **For any two interleavings $\pi_1, \pi_2$ of the same multiset of confirmation messages, applied to the same initial state $\sigma_0$:**
> $$
> \text{apply}(\sigma_0, \pi_1) = \text{apply}(\sigma_0, \pi_2)
> $$
> **restricted to the joint state of $(L_{13}, \text{SettlStatus}, L_{15})$.**

**Parent**: `ledger_data_v1.0` Λ_8 (replay determinism), v10.3 P9 (lifecycle purity), nazarov INV-DS-4.

**Classification**: runtime, discharged by property-based test (multi-permutation replay with byte-identical state assertion).

**Severity if violated**: CRITICAL. Time-travel and audit reconstruction become inconsistent; restated history cannot be reproduced.

**Equivalent formulation** (nazarov, lattice form): the FSM transition function `step(state, witness_set) → state'` is a pure function of the *witness multiset*, not the witness sequence. This is the strongest form: it makes order-independence a definitional property, not a coincidence.

### DS6 — Idempotency of Finality Messages

> **For any confirmation message $c$ targeting obligation $o$:**
> $$
> \text{ingest}(c) \circ \text{ingest}(c) = \text{ingest}(c)
> $$
> **i.e., re-presenting the same message (same `external_message_id` or equivalent dedup key) twice has no incremental effect on $L_{13}$, `SettlStatus`, or $L_{15}$.**

**Parent**: v10.3 P5 (transaction idempotency), v10.3 P6 (lifecycle idempotency), data-spec N_4 (idempotency on replay), data-spec B_12 (signal idempotency keys).

**Classification**: runtime, enforced at ingest by content-addressed deduplication.

**Severity if violated**: HIGH. Double-processing of confirmations; obligation FSM may transition twice; CSDR penalty may be paid twice.

### DS7 — Failure Non-Reversal (FAILED does not undo position)

> **For every settlement obligation $o$ and every transition $o.\text{state}: \text{Pending} \to \text{Failed}$:**
> $$
> \forall w \in \mathcal{W}_{\text{real}}, \forall u : w_{\text{after-fail}}(u)[\text{own}] = w_{\text{before-fail}}(u)[\text{own}]
> $$
> **i.e., no move on a real wallet's `own` coordinate is emitted as a consequence of a settlement-fail event.**

**Parent**: v10.3 §8.4 (the "no reversal on fail" paragraph), v10.3 FAQ Q5, IFRS 9.B3.1.3 (regular-way trades not derecognised on fail), CRR Article 379 (capital treatment of failing trades).

**Classification**: hybrid. Compile-time enforced by capability-typing on `own` write-handlers (the settlement-fail handler does not have the capability to write `own`; only `CORRECTION`-class transactions do, with named approver and four-eyes — jane_street §10, ashworth §4.2, finops, lattner). Runtime confirmed by mutation testing.

**Severity if violated**: CRITICAL. The economic position becomes a function of operational settlement timing; PnL volatility is artificially suppressed; regulatory reporting becomes wrong.

**Note on the only legal exception**: a `CORRECTION` transaction (a fresh transaction with explicit anti-moves, four-eyes approval, named requester, named approver) is the *only* legal path that removes a position post-T. It is itself timestamped at correction-time, not retroactively at T. Per jane_street §10 ("the rule you regret breaking").

### DS8 — Status Monotonicity within Terminal-Set Semantics

> **For every settlement obligation $o$, the lifecycle FSM transitions only in the order:**
>
> $\textsc{Pending} \to \textsc{Instructed} \to \{\textsc{Settled}, \textsc{Failed}, \textsc{PartiallySettled}\}$
>
> **with the only legal retrograde edges:**
> $$\textsc{Failed} \to \textsc{Instructed} \quad\text{(re-instruction, post buy-in)}$$
> $$\textsc{PartiallySettled} \to \textsc{Instructed} \quad\text{(continue settling residual)}$$
>
> **No path back to $\textsc{Pending}$ exists. No path out of $\{\textsc{Settled}, \textsc{Cancelled}, \textsc{BoughtIn}, \textsc{Defaulted}\}$ exists; these are absorbing.**

**Parent**: v10.3 §11.7 (the original four-state FSM), `ledger_data_v1.0` §3 L_15 obligation FSM (Pending→{Discharged|Compensated|Defaulted}).

**Classification**: compile-time, encoded as the closed-sum `lifecycle_stage` enum + the `step` function being total over `(state, event)` pairs (per minsky §8.2, jane_street §1.2, lattner §3, halmos I3).

**Severity if violated**: HIGH. FSM regressions break replay determinism and audit reconstruction; an `Settled → Failed` re-transition would invalidate everything downstream of the original settlement (manufactured-dividend claims, recall composition, PnL).

**Note on re-instruction**: the retrograde edge `Failed → Instructed` is recorded as a *new substate transition* with its own timestamp, not as a rewrite of the previous state. The append-only log preserves the full trail. (Per jane_street I-4.)

### DS9 — Buy-In Compensation Closure (CSDR / Reg SHO)

> **For every settlement obligation $o$ that transitions to `Failed` and is not cured by re-instruction within the regulatory grace period $\Delta_{\text{CSDR}}$:**
> $$
> \exists \tau_{\text{buyin}} \in L_{13},\, \exists o_{\text{buyin}} \in L_{15} : \tau_{\text{buyin}}.\text{type} = \textsc{Buyin} \wedge o.\text{compensation\_handler} = \kappa_{\text{buyin}}(\tau_{\text{buyin}}, o_{\text{buyin}})
> $$
> **i.e., every fail past the grace period spawns a buy-in transaction with its own settlement obligation, and the original obligation transitions to $\textsc{Compensated}$ via the buy-in, $\textsc{BoughtIn}$ status, or $\textsc{Defaulted}$ if the buy-in itself fails.**

**Parent**: `ledger_data_v1.0` Λ_13 (obligation liveness), v10.3 §13 P21, CSDR Article 7(3), Reg SHO Rule 204.

**Classification**: runtime, discharged by Temporal workflow timer + saga compensation (per temporal §7, jane_street §6).

**Severity if violated**: HIGH. Open obligations persist past regulatory deadlines; CSDR penalties accrue indefinitely; failed trades stay on books.

**Note on closed-sum**: the buy-in regime enumeration must itself be a closed sum (`CSDRMandatoryBuyIn | GMSLA_2018 | GMRA_2011 | BilateralContractual` per matthias §5.3 Gap 9). This is a real proof obligation — see §7 G1.

### DS10 — Cross-Currency Herstatt Visibility (asymmetric leg states)

> **For every cross-currency trade $\tau$, the trade emits a parent obligation $o_{\text{fx}}$ with two child obligations $o_{\text{ccy1}}$, $o_{\text{ccy2}}$, each carrying its own settlement-date and discharge witness. The parent's discharge predicate is the conjunction:**
> $$
> D_{\text{fx}}(\sigma) = (o_{\text{ccy1}}.\text{state} = \textsc{Discharged}) \wedge (o_{\text{ccy2}}.\text{state} = \textsc{Discharged})
> $$
> **The Herstatt-window invariant: at every time $t$, exactly the open obligations whose `state` is non-terminal are visible as quantified exposure to counterparty default.**

**Parent**: v10.3 §2.6 (Herstatt risk paragraph), `ledger_data_v1.0` Λ_15 (cross-CCP novation; analogue for cross-currency).

**Classification**: runtime; the asymmetric-state period is observable via a projection over $L_{15}$.

**Severity if violated**: HIGH. The framework cannot quantify Herstatt exposure; the regulatory disclosure (CRR Article 442 / IFRS 7.B11) is incomplete.

**Note**: the framework does not eliminate Herstatt risk (no ledger design can — v10.3 §2.6 explicitly states this). It *names* the risk, *quantifies* the exposure, *routes* the compensation, and *audits* the loss. CLS / PvP infrastructure mitigates externally; the ledger represents the mechanism that applies (per matthias §6.10, halmos §5.1, formalis Phase 1 §7, noether §5.4, geohot §6/F7, cartan §8.2).

### DS11 — Partial-Settlement Conservation

> **For every partial settlement event with $q' < q$ delivered, $q - q'$ remaining:**
> 1. The original obligation $o$'s state transitions to $\textsc{PartiallySettled}$.
> 2. The economic position (real wallet `own`) is **unchanged** by the partial-settle event itself — the original $\tau$ recognised the full $q$ at $T$.
> 3. A child obligation $o_{\text{rem}}$ is registered with `parent_obligation_id = o.id`, $q_{\text{rem}} = q - q'$, $t_d^{\text{rem}}$ = original $t_d$ extended per CSDR / regime.
> 4. Conservation holds: $q_{\text{rem}} + q' = q$ (sum-of-children-equals-parent).

**Parent**: v10.3 §11 P9 (lifecycle purity, applied to the partial-fill state-only transitions), `ledger_data_v1.0` §3 L_15 partial discharge.

**Classification**: runtime, discharged by property-based test (per testcommittee P_DS_9 monotonicity-of-obligation-through-partials).

**Severity if violated**: HIGH. Partial fills cause silent quantity drift; CSDR penalty is computed on the wrong residual.

**Termination concern (cap on recursion depth)**: a residual itself can partially settle, recursively. jane_street §6 caps depth at 2; sbl/temporal/karpathy allow recursion. The Settlement Team must decide and pin the bound. **See PO-9.**

### DS12 — Variant Degeneration (T+1 is a parameter)

> **The deferred-settlement representation is parameterised on `settle_date = t_d` and degenerates uniformly across:**
> - **T+0 (atomic on-chain DvP)**: $t_d = T$, the obligation is issued and discharged in the same atomic transaction; the `Pending` state has zero duration.
> - **T+1 (US equities post-2024, UK/EU 2027)**: $t_d = T + 1$ business day; FSM unchanged.
> - **T+2 (canonical case)**: $t_d = T + 2$ business days.
> - **T+5+ (some emerging markets)**: $t_d = T + n$ business days, parameterised in `ProductTerms[u].settlement_cycle` per `L_4` CalendarConvention.
>
> **For all variants, DS1–DS11 hold without modification; only the workflow timer durations change.**

**Parent**: v10.3 §11 P0 (uniform settlement model), tokenised-settlement compatibility (isda §8.5, geohot §F2, lattner §7.6, sbl §6.3).

**Classification**: structural; degeneration is the consequence of $t_d$ being a workflow parameter, not a hardcoded constant.

**Severity if violated**: MEDIUM. T+1 transition or T+0 tokenisation becomes a multi-quarter migration rather than a config change.

### DS13 — Reconciliation Pair Anchoring (data-spec L_6 specialisation)

> **The reconciliation pair on $L_6$ (PositionState) is a daily T+1 morning identity check between the ledger and the external custodian/CSD report, parameterised by settlement status:**
> $$
> \text{Reconciled}(t) \iff \forall \tau : \text{SettlStatus}(\tau)(t) \in F_{\text{terminal}} \;\Rightarrow\; \Pi_{\text{ledger}}(\tau, t) = \Pi_{\text{external}}(\tau, t)
> $$
> **i.e., ledger and external agree on every transaction in a terminal state, and the lead-lag is *exactly* the sum of non-terminal obligations (DS3).**

**Parent**: data-spec L_6 reconciliation pair (CCP/custodian/triparty, daily T+1, per-regime tolerance, `wf-position-break` workflow).

**Classification**: runtime, daily T+1 cron workflow + signal-driven on-confirmation.

**Severity if violated**: MEDIUM. Operational; recon report becomes opaque (cannot distinguish lag from break).

### DS14 — CSDR Penalty Schema Determinism

> **For every settlement obligation $o$ in `Failed` state at end-of-day $t > t_d$, a CSDR penalty obligation $o_{\text{pen}} \in L_{15}$ is registered atomically with the day-end roll, with payload:**
> $$
> o_{\text{pen}} = \langle \text{rate\_basis\_points}, \text{days\_late}, \text{source\_lei}, \text{currency}, \text{notional} \rangle
> $$
> **where the penalty rate is selected by a pure function from the versioned CSDR rate matrix (per `ledger_data_v1.0` §CSDR Penalty Schema), pinned by `VersionPinSidecar`.**

**Parent**: `ledger_data_v1.0` §Operational-CSDR (CSDR penalty schema), CSDR Article 7(2), Commission Delegated Regulation (EU) 2017/389.

**Classification**: runtime, with the penalty function being a pure deterministic projection over the obligation log + the pinned rate-matrix snapshot.

**Severity if violated**: MEDIUM. Penalty mis-attribution; auditors will demand reconciliation against CSD's penalty notification, which the framework computes independently and reconciles to (per jane_street §12 — the CSD wins for booking, but the framework's number is in the audit trail).

### DS15 — Counterparty Default Close-Out Routing

> **If a counterparty $c$ defaults at time $t_{\text{def}} \in [T, t_d^+]$, every open settlement obligation against $c$ transitions to $\textsc{Compensated}$ via the close-out-netting compensation handler, and the close-out value is computed per ISDA Master Agreement (or analogous bilateral terms) at $t_{\text{def}}$.**

**Parent**: v10.3 §13 close-out netting, ISDA close-out terms, jane_street §10 Lehman-scenario, cartan §4.7 default close-out.

**Classification**: runtime; the trigger is a `LifecycleOracle` event of kind `CounterpartyDefault`.

**Severity if violated**: HIGH. Counterparty defaults during the open window are not handled cleanly; legal close-out diverges from ledger position.

### DS16 — Bitemporal Restatement, Never Mutation

> **When a CSD or custodian issues a correction (a restatement of a prior confirmation), the original $L_{11}$ row is preserved (with its `t_known` of original ingest); a new row is appended with the same `t_obs` but the new `t_known`. The obligation's `corrections_chain` grows by one. The two query modes `as_of(t_known)` and `with_corrections_through(t_known')` are first-class.**

**Parent**: data-spec N_9 (bitemporal mode definitions), Λ_4 (bitemporal coherence), nazarov INV-DS-5.

**Classification**: runtime, structural (immutable append-only log).

**Severity if violated**: HIGH. Time-travel and audit reconstruction become inconsistent under restated confirmations; IFRS 13 audit reconstruction breaks.

### DS17 — Capability Scoping on Settlement Status Writes

> **Each `SettlStatus(\tau)` field has a unique writer: the `SettlementWorkflow` of v10.3 §11.5 / `ledger_data_v1.0` Operational-Saga. No other handler (post-trade gateway, trader, risk system, regulatory reporter) may mutate it. They may read per their capability; writes are gated.**

**Parent**: StatesHome C11 (capability scoping per field), `ledger_data_v1.0` Λ_14 (capability-scope check).

**Classification**: compile-time, enforced by phantom typing on the write capability (per minsky's `exposure_bearing` / `custody_bearing` discipline, jane_street's I-1 capability tagging).

**Severity if violated**: HIGH. Settlement status drift becomes possible; the FSM is no longer the source of truth.

### DS18 — DvP Ledger-Level Atomicity

> **For every settlement-typed transaction $\tau$ that contains both a securities leg and a cash leg (DvP), the executor commits both legs atomically: both apply or neither does, observable as a single `StateDelta`.**

**Parent**: v10.3 P2 (atomic commitment), v10.3 §8.4, StatesHome C3 (atomic StateDelta), minsky I-DEF-12.

**Classification**: structural, at the executor primitive.

**Severity if violated**: CRITICAL. DvP is broken at the ledger level; conservation cannot be guaranteed across legs.

**Note on settlement-level DvP (P_DS_12 in testcommittee, minsky I-DEF-3)**: distinct from ledger-level atomicity. Settlement-level DvP at the CSD is provided by external infrastructure (DTC, T2S, Euroclear). The framework's response when CSD-side DvP fails (cash leg confirms but securities leg fails, or vice versa) is the asymmetric-leg case — see DS-DvP-PO in §7 (G3).

---

## 2. Totality arguments — workflows, preconditions, postconditions, termination

We enumerate the top-level workflows and prove totality of each. For each, we state: precondition, postcondition, termination predicate (with bound), and the closed-sum signal universe over which `step` is total.

### Workflow 1: SettlementSaga

**Precondition**: a committed SETTLEMENT-typed transaction $\tau$ in $L_{13}$ with associated obligation $o = o_{\text{settle}}(\tau)$ in $L_{15}$.

**Step function signature** (per minsky §8.2):
$$
\text{step}: (s \in S_{\mathfrak{O}}) \times (e \in \Sigma_{\text{settlement}}) \to (s' \in S_{\mathfrak{O}}) \cup \{\text{Reject}(s, e)\}
$$
where $S_{\mathfrak{O}} = \{\textsc{Pending, Instructed, PartiallySettled, Settled, Failed, BoughtIn, Cancelled, Defaulted}\}$ and $\Sigma_{\text{settlement}}$ is the closed-sum settlement-confirmation event universe (sese.023, sese.024, sese.025, sese.027, camt.054, deadline-fire, manual-override-with-witness).

**Totality**: `step` is exhaustive over $S \times \Sigma$; every (state, event) pair has either a defined successor or an explicit `Reject` (per StatesHome C2 totality, jane_street §1.2 closed-sum, halmos I3, minsky §3.2 transition table).

**Postcondition**: $o.\text{state} \in F_{\text{terminal}} = \{\textsc{Settled}, \textsc{Cancelled}, \textsc{BoughtIn}, \textsc{Defaulted}\}$ within bounded time $t_d + \Delta_{\text{CSDR}} + \Delta_{\text{escalation}}$.

**Termination predicate**:
$$
\text{terminated}(o) \;\equiv\; o.\text{state} \in F_{\text{terminal}}
$$
with bound $T^* = t_d + \Delta_{\text{CSDR}} + \Delta_{\text{escalation}} \leq T + n_{\max}$ where $n_{\max}$ is the regulatory horizon (CSDR Article 5: 60 days; data-spec $\Delta_h = 90$ days for SETTLEMENT_INSTRUCTION). **Termination is dependent on the cluster-availability assumption (G8).**

### Workflow 2: BuyInWorkflow

**Precondition**: an obligation $o$ in `Failed` state with `compensation_handler = κ_{buyin}` and `buyin_deadline` reached.

**Postcondition**: $o.\text{state} \in \{\textsc{BoughtIn}, \textsc{Defaulted}\}$; if $\textsc{BoughtIn}$, a fresh buy-in transaction $\tau_{\text{buyin}} \in L_{13}$ exists with its own SettlementSaga child.

**Termination**: bounded by the buy-in regime's deadline ($T+4$ for liquid CSDR equities, $T+7$ for SME-growth, $T+15$ for illiquid). The buy-in transaction itself triggers a fresh SettlementSaga; recursion is bounded because the buy-in trade is at market-clearing price and the buyer is not the failing party.

**Recursion termination argument**: a buy-in's own settlement may itself fail. The framework caps recursion depth at $D_{\text{max}}$ (jane_street §6 caps at 2; sbl/temporal allow more). **PO-9 below**: the Settlement Team must pin $D_{\text{max}}$ and prove that beyond depth $D_{\text{max}}$ the cascade transitions to `Defaulted` rather than continuing to spawn buy-ins.

### Workflow 3: CSDRPenaltyAccrual

**Precondition**: a scheduled cron firing at end-of-day $t > t_d$, an obligation $o$ in `Failed` state.

**Step**: a pure deterministic computation `accrue(o, t) → cash_move` per the versioned CSDR rate-matrix.

**Totality**: the rate-matrix is a closed sum over instrument-class × duration-band; pinned by `VersionPinSidecar`; `accrue` is total over its closed domain.

**Postcondition**: a small cash transaction is committed from the failing party's wallet to the receiving party's wallet, atomically with a state-only update on $o.\text{csdr\_penalty\_accrued}$.

**Termination**: bounded; the accrual stops on $o$ reaching a terminal state.

**Subtlety (G5)**: late-arriving discharge after penalty accrual has commenced. If the discharge resolves before the penalty cycle has externalised (paid via CSD), the saga compensation tower's policy is `cancel-compensation` (per `ledger_data_v1.0` Operational-Saga "Late-discharge race policy"). If the cycle has externalised, the policy is `queue-and-reconcile`. **The Settlement Team must confirm the SETTLEMENT entry exists in the policy table** — see PO-2.

### Workflow 4: CorrectionTransaction

**Precondition**: a settlement-typed transaction $\tau$ that needs to be cancelled (mutual cancellation, trade bust, or post-fail unwind), four-eyes approval, named requester and approver.

**Postcondition**: a fresh transaction $\tau_{\text{corr}}$ in $L_{13}$ with explicit anti-moves (timestamped at correction-time, not retroactively at $T$); the original $\tau$ remains in the move stream (P4 log monotonicity); $o.\text{state} = \textsc{Cancelled}$; affected obligation registered as `Compensated`.

**Totality**: the correction-handler is total over the closed sum of `CorrectionReason ∈ {MutualBust, OperationalError, RegulatoryOverride}`.

**Termination**: trivial; one transaction.

### Workflow 5: CrossCurrencyDvP (Herstatt)

**Precondition**: a cross-currency trade with two currency legs in different time zones; two child obligations $o_{\text{ccy1}}$, $o_{\text{ccy2}}$ registered atomically.

**Postcondition**: the parent obligation $o_{\text{fx}}$ reaches `Discharged` iff both children reach `Discharged`; otherwise transitions via Herstatt-specific compensation $\kappa_{\text{Herstatt}}$.

**Termination**: bounded by the later of the two leg-deadlines plus regulatory grace.

**The Herstatt window** is the time interval during which exactly one of the two legs is `Discharged` and the other is in a non-terminal state. This is a *measurable*, *queryable* property of the obligation set, exposed via a projection.

### Workflow 6: CorporateActionInWindow

**Precondition**: a corporate action with record date $r \in [T, t_d]$, affecting unit $u$ for which an open settlement obligation $o$ exists.

**Postcondition**: the discharge predicate of $o$ is *re-evaluable under bitemporal restatement* — the `target quantity` field updates per the corporate-action StateDelta. A separate manufactured-payment obligation may be registered for cum-dividend trades (entitlement attaches to the economic owner at $r$, regardless of custody).

**Totality**: the corporate-action handler is total over the closed sum of `CorporateActionType ∈ {CashDividend, StockSplit, Spinoff, RightsIssue, MergerCash, MergerStock, ...}` (gap noted: G3 — CDM `CorporateActionType` enum stability).

**Subtlety (G3)**: discharge predicates must be *bitemporal-state-functions*, not snapshot values frozen at $T$. **PO-4** below.

---

## 3. Liveness theorem — every open obligation reaches a terminal state

> **Theorem DS-Liveness.** *For every settlement obligation $o$ registered at time $T$ with intended deadline $t_d$, there exists a finite time $T^* \leq T + n_{\max}$ such that:*
> $$
> o.\text{state}(T^*) \in F_{\text{terminal}} = \{\textsc{Settled}, \textsc{Cancelled}, \textsc{BoughtIn}, \textsc{Defaulted}, \textsc{Compensated}\}
> $$

**Proof structure**: inherits from `ledger_data_v1.0` Λ_13 (Obligation Liveness) + the data-spec §13.2.7 five-lemma proof. The five lemmas:

1. **Lemma 1 (Timer arming)**: every obligation has a deadline timer armed at registration. Discharged by Temporal workflow timer durability + saga-tower discipline.
2. **Lemma 2 (Confirmation matching)**: every confirmation message is matched to its obligation by content-addressed dedup. Discharged by L_11 ExternalConfirmation contract + UTI/EndToEndId discipline (with caveat G2).
3. **Lemma 3 (FSM transition completeness)**: the `step` function is total over $(S, \Sigma)$ (DS8). Discharged by closed-sum + exhaustive pattern match.
4. **Lemma 4 (Compensation handler totality)**: every $o$ has a defined $\kappa$ for every failure type. Discharged by closed-sum on `failure_type` (with caveat G1: open-ended ISO 20022 free-text reasons must be normalised).
5. **Lemma 5 (Externalisation bound)**: the compensation reaches a terminal state in bounded steps. Discharged by saga-tower depth bound + late-discharge race policy.

The five lemmas carry over from Λ_13 verbatim. **The framework cannot prove DS-Liveness without G1 (closed sum on CSD failure types) and G8 (bounded cluster outage)** — these are the genuine open obligations.

---

## 4. Replay determinism theorem — same external messages, replayed in canonicalised order, produce same ledger state

> **Theorem DS-Replay.** *For any two interleavings $\pi_1, \pi_2$ of the same multiset of confirmation messages, applied to the same initial state $\sigma_0$, the same canonicalisation function $\text{canon}$ produces:*
> $$
> \text{canon}(\text{apply}(\sigma_0, \pi_1)) = \text{canon}(\text{apply}(\sigma_0, \pi_2))
> $$
> *restricted to $(L_{13}, \text{SettlStatus}, L_{15})$.*

**Proof structure**: inherits from `ledger_data_v1.0` Λ_8 (Replay Determinism) + data-spec B_12 (signal idempotency keys with deterministic merge order via lex-sort on `(t_known, message_id)`).

**Key sub-lemmas**:

- **L_R1**: each confirmation $c$ carries an `external_ref` matching exactly one $\tau$ (with caveat G2: matching is heuristic in the absence of UTI).
- **L_R2**: the state delta for a confirmation $c$ matched to $\tau$ depends only on $\tau$ and $c$, not on the order in which other unrelated confirmations have been processed.
- **L_R3**: $L_{15}$ FSM transitions are commutative across distinct obligations: $\text{discharge}(\tau_1) \circ \text{discharge}(\tau_2) = \text{discharge}(\tau_2) \circ \text{discharge}(\tau_1)$ as state operators on disjoint obligation rows.
- **L_R4**: confirmations emit no economic moves (DS7); conservation is unaffected by reordering.

Hence the algebra is commutative on disjoint settlement workflows, idempotent on duplicates (DS6), and replay is deterministic.

**Strongest formulation (nazarov)**: the FSM transition function `step(state, witness_set) → state'` is a *pure function of the witness multiset*, not of the witness sequence. Order-independence is then a definitional property.

**Caveats** (G2, G5): replay determinism fails if (a) confirmation matching is heuristic (multi-trade UTI ambiguity) or (b) a discharge confirmation is itself restated retroactively. Both are explicitly named gaps.

---

## 5. Type-vs-runtime decomposition — which invariants are compile-time vs runtime

This is the cartan/minsky/jane_street/lattner question. We give an honest decomposition. Each invariant is one of: (CT) compile-time enforceable, (RT) runtime-discharged, (HY) hybrid.

| Invariant | Classification | Mechanism |
|---|---|---|
| DS1 — Economic-exposure-at-T | **HY** | (CT) capability typing on `own` write-handlers; (RT) property-test that PnL is independent of `lifecycle_stage` |
| DS2 — Conservation | **RT** | StatesHome C2 structural argument per event-class handler |
| DS3 — Reconciliation identity | **RT** | property-test; sign convention pinned by §9 PO-3 |
| DS4 — No discharge without witness | **HY** | (CT) FSM transition function takes witness as input parameter; (RT) cryptographic verification |
| DS5 — Replay determinism | **RT** | property-test (multi-permutation replay) |
| DS6 — Idempotency of finality | **RT** | content-addressed dedup at ingest |
| DS7 — Failure non-reversal | **HY** | (CT) capability typing on settlement-fail handler (no `own` write capability); (RT) mutation testing |
| DS8 — Status monotonicity | **CT** | closed-sum FSM + exhaustive pattern match on `step` |
| DS9 — Buy-in compensation closure | **RT** | Temporal workflow timer + saga-tower discipline |
| DS10 — Herstatt visibility | **RT** | projection over $L_{15}$ |
| DS11 — Partial conservation | **RT** | property-test on monotonicity-of-residual |
| DS12 — Variant degeneration | **CT** | $t_d$ is a workflow input parameter, not a hardcoded constant |
| DS13 — Reconciliation pair anchoring | **RT** | daily T+1 cron workflow |
| DS14 — CSDR penalty schema determinism | **RT** | pure function from versioned rate-matrix |
| DS15 — Counterparty default close-out | **RT** | LifecycleOracle event handler |
| DS16 — Bitemporal restatement | **CT** | append-only log structure |
| DS17 — Capability scoping | **CT** | phantom typing on writer capability |
| DS18 — DvP ledger-level atomicity | **CT** | executor primitive guarantees atomic StateDelta |

**Summary**: 6 CT, 9 RT, 3 HY out of 18. The compile-time investment is non-trivial — minsky §9 honestly notes the cost of phantom-typing every unit. The Settlement Team must decide whether to take that cost. **Our recommendation**: take it for DS17 (capability scoping) and DS7 (failure non-reversal); these are the invariants whose violations are silent and economically catastrophic. The other CT items (DS8, DS12, DS16, DS18) are nearly free.

---

## 6. Cardinality of the open-window state space (for testcommittee TLA+ model checker)

For the joint product space `Status × ObligationFSM`:

- **Status** $|S_{\text{settl}}| = 7$: {Executed, Instructed, PartiallySettled, Settled, Failed, BoughtIn, Cancelled}.
- **Obligation FSM** $|S_{\mathfrak{O}}| = 5$: {Pending, Attempted, Discharged, Compensated, Defaulted}.
- **Joint product before pruning** = $7 \times 5 = 35$.
- **Reachable subset (after pruning impossible combinations like `Settled × Pending`)**: ~12 states. **Finite.**
- **Absorbing states**: `(Settled, Discharged)`, `(BoughtIn, Compensated)`, `(Cancelled, Compensated)`, `(_, Defaulted)`. Four absorbing states.

For the TLA+ model parameters $|\mathcal{W}| = 3, |U| = 2, \text{depth} \le 6$ (per StatesHome addendum bound, testcommittee §8.5):

- **Wallet × unit pairs**: $3 \times 2 = 6$ position rows.
- **Per row, position is bounded** (StatesHome bounded-size invariant).
- **Trade events × confirmation events** at depth 6: ~$10^4$ event sequences.
- **Reachable joint state space** (estimated, per testcommittee §8.5 + lattner §10): $10^5$–$10^6$ states.

**Tractability**: TLC-tractable on a workstation in minutes. **Conservation and pending-mirror violations** show up at depth ≤ 2; **status-monotonicity violations** at depth ≤ 4; **liveness counterexamples** at depth ≤ 8.

**Recommendation**: testcommittee must run the TLA+ check at $|\mathcal{W}|=3, |U|=2, \text{depth}=8$ with all 18 invariants encoded. **Required to pass before the deferred-settlement specification is considered formally verified.**

---

## 7. Honest gap list — proof obligations the framework CANNOT discharge without further constraints

Each gap is named, the constraint that would close it is stated, and the consequence of leaving it open is explicit.

### G1 — Closedness of CSD failure-type enumeration

**Gap**: DS9 (buy-in compensation closure) requires $\kappa_{\text{settle}}$ to be total over a closed sum of failure types. CSDs in practice publish failure reasons as ISO 20022 status codes, but the practical reason field (`Reason4Choice` etc.) is open-ended in some message variants and free-text in others.

**Constraint to close**: produce a normalised CSD-failure-reason closed sum, with a documented mapping from each CSD's enum, with `OTHER → ESCALATE_HUMAN` as a defined sink. Pin the enum version per `ledger_data_v1.0` §3 versioning algebra.

**Consequence of leaving open**: DS9 totality is contingent on a manual-fallback path. Liveness (DS-Liveness) cannot be proven for `OTHER`-tagged fails until human escalation discharges them.

**Owner**: matthias (CDM cross-walk), isda (regulatory mapping).

### G2 — Confirmation matching in the absence of UTI

**Gap**: DS5 (replay determinism) requires confirmation-to-trade matching to be a *total deterministic function*. With UTI / EndToEndId discipline, this holds. Without (some markets, some failures of issuer-side reporting), matching is heuristic: same-ISIN-same-counterparty-same-quantity-same-date. This is non-deterministic when multiple trades match.

**Constraint to close**: state the matching contract explicitly. If the contract requires UTI, reject and quarantine non-UTI confirmations to $L_{18}$ rather than forcing a match. Add a property test that ambiguous confirmations are quarantined, never silently mis-matched.

**Consequence of leaving open**: DS5 is conditional on "all matches resolved by ingest time". DS-Replay theorem becomes provisional.

**Owner**: temporal (workflow-level), nazarov (boundary-level), matthias (CDM).

### G3 — Bitemporal predicate evaluation under corporate action

**Gap**: discharge predicates registered at $T$ encode "deliver 100 shares". After a 2-for-1 split before $t_d$, the predicate must refer to "200 shares". If the predicate is a closed-over snapshot, the system mis-evaluates at $t_d$.

**Constraint to close**: enforce that all $L_{15}$ discharge predicates are *bitemporal-state-functions*, not snapshot values, and that they read from the latest `with_corrections_through` knowledge time. This is a typing requirement on $L_{15}$ `DischargePredicateKind`. Verify by property test: introduce a corporate action between obligation registration and obligation deadline; verify discharge fires correctly with the post-CA quantity.

**Consequence of leaving open**: DS-Liveness fails for any obligation whose product undergoes a fungibility-breaking corporate action mid-window.

**Owner**: matthias (corporate-action modelling), correctness (property-test fixtures).

### G4 — DvP leg-inconsistent failure compensation

**Gap**: a CSD reports cash leg `Settled`, securities leg `Failed` (rare but real at non-DvP CSDs, or in CLS-non-eligible cross-currency trades). The framework can name the failure type `LEG_INCONSISTENT` but the *correct* compensation is genuinely contingent on legal regime, CSD, and operational practice.

**Constraint to close**: catalogue per CSD. For DTC: PvP-style — leg-inconsistency triggers manual ops workflow. For non-DvP CSDs: standard κ is reverse-the-partial-leg-by-market-trade. Capture per CSD in `ReferenceMaster` ($L_{16}$) and dispatch κ accordingly.

**Consequence of leaving open**: DS-Liveness depends on a manual operations path; the framework cannot prove totality of DS9 without committing to a definition.

**Owner**: ashworth (audit-side controls), isda (regulatory mapping), jane_street (operational runbook).

### G5 — Replay determinism in the presence of restated confirmations

**Gap**: a CSD may restate a confirmation: yesterday "Settled, q=100"; today "Settled, q=60, the rest was a system error". The bitemporal apparatus supports this in principle. But a *settlement workflow that already concluded* on yesterday's confirmation cannot be "un-concluded" — Temporal workflow histories are append-only and idempotent in the forward direction, not the reverse.

**Constraint to close**: define how an obligation that has reached `Discharged` reacts to a corrective restatement. Two design choices: (a) treat the restatement as a *new* obligation (clean separation, append-only); (b) extend the obligation FSM with a `Reopened` state. Choice (a) is simpler and aligns with append-only discipline; **we recommend (a)**.

**Consequence of leaving open**: DS5 and DS-Replay do not currently cover restated discharging confirmations.

**Owner**: temporal (workflow design), nazarov (envelope discipline).

### G6 — Cross-jurisdiction CSDR vs SEC vs T+1 vs T+2

**Gap**: $t_d$ is jurisdiction-dependent (US T+1 since May 2024, EU T+2 currently, UK T+1 from October 2027, Asia mostly T+2). For a global firm with a single ledger, the *same* security on the *same* trade date can have different $t_d$ depending on venue/CSD. The discharge deadline is a function of $\tau$'s execution venue and clearing path, not of the trade alone.

**Constraint to close**: confirm $t_d$ is sourced from the CDM `tradableProduct.settlementTerms.settlementDate` as resolved by the venue / CSD reference data, not hardcoded. Verify by property test across the closed sum of `MIC × ISIN × CSD` triples.

**Consequence of leaving open**: T+1 transition becomes a multi-quarter migration project rather than a config change (DS12 violation).

**Owner**: matthias (CDM mapping), isda (regulatory roadmap).

### G7 — The "true at T+2⁻" semantics — time-of-day convention

**Gap**: "Reconciles to nostro at T+2" is sharp at $t_d^+$ (after CSD batch). At $t_d^-$ (morning of T+2 before CSD batch), the nostro has not been updated; reconciliation at $t_d^-$ deliberately shows InFlight = quantity-of-the-pending-trade. This is correct but might surprise an auditor.

**Constraint to close**: state the time-of-day convention explicitly, anchored to the relevant CSD's batch settlement time. Cite $L_{19}$ ClockAuthority for canonical timestamps.

**Consequence of leaving open**: cosmetic but real — the spec is unclear on which side of the CSD batch reconciliation runs.

**Owner**: jane_street (operational runbook), nazarov (timestamp discipline).

### G8 — Liveness under prolonged Temporal cluster outage

**Gap**: liveness is *eventual* under cluster outage, not instantaneous. For a deferred-settlement obligation, this means: if the cluster is down across $t_d$, the discharge timer fires after recovery, possibly past CSDR penalty windows. The framework cannot eliminate this — the timer fires in the workflow's logical time, not wall-clock time, and external regulatory deadlines tick in wall-clock time.

**Constraint to close**: not closable by formal proof. Mitigated by multi-region replication, an external watchdog (a non-Temporal check that Temporal timers are firing on schedule), and an SLA on cluster availability.

**Consequence of leaving open**: DS-Liveness explicitly assumes cluster availability at $t_d$. Stated honestly as an operational assumption, not a proven property.

**Owner**: temporal (cluster operations), jane_street (operational runbook).

### G9 — Late-discharge race policy table coverage

**Gap**: the saga compensation tower's "Late-discharge race policy" must have a `SETTLEMENT` entry pinned in `VersionPinSidecar`. correctness's B-Q-2 (Phase 1) noted this is *inferred* from the saga-tower text, not confirmed.

**Constraint to close**: confirm or add the explicit `SETTLEMENT` entry: `cancel-compensation if not externalised; otherwise queue-and-reconcile`. Pin per `VersionPinSidecar`.

**Consequence of leaving open**: late-arriving discharge after deadline timer fired is undefined behaviour; replay determinism contingent.

**Owner**: temporal (workflow-tower), correctness (test-coverage).

### G10 — Herstatt elimination vs representation

**Gap**: the framework *names* Herstatt risk (DS10) but does not *eliminate* it. CLS / PvP infrastructure mitigates externally; the ledger represents whichever real-world mechanism applies.

**Constraint to close**: not closable in the ledger. The risk is real and external. The framework's contribution: name it, quantify it, route the compensation, audit the loss.

**Consequence of leaving open**: stated honestly. Cross-currency trades carry residual settlement risk that the ledger represents but does not prevent.

**Owner**: framework-wide (acknowledged at v10.3 §2.6).

### G11 — Manufactured payment / claim recipient determination

**Gap**: corporate action with record date $r \in (T, t_d]$. Trade-date accounting (DS1) says the buyer is economically entitled. CSD inscription says the seller (still on register) receives the dividend. Manufactured payment (seller → buyer) reconciles, but: which jurisdiction? Which contract? What if the seller has gone bankrupt before the dividend pays out?

**Constraint to close**: codify per-jurisdiction the manufactured-payment rule, with the seller's obligation registered as a separate L_15 row (`obligation_kind = MANUFACTURED_DIVIDEND`) and its own discharge predicate.

**Consequence of leaving open**: corporate-actions-in-window are a known frequent error source (per ashworth §6.8). The framework's design absorbs this via separate obligations, but the per-jurisdiction rule is not fully specified.

**Owner**: ashworth (accounting), matthias (CDM `CorporateAction`), isda (regulatory).

### G12 — Single-source escape on attestation

**Gap**: nazarov's TA-DS-10 — is a single attestor (e.g., only the CSD, not the custodian) sufficient to discharge an obligation? The data-spec aggregation rule defaults to "primary CSD attestation suffices, OR 2-of-2 from secondary + tertiary." Single-source escape is permitted only with a registered authority assumption.

**Constraint to close**: maintain the trust-assumption registry (TA-DS-1 through TA-DS-10), with named owners and detection signals for each. Quarterly review.

**Consequence of leaving open**: single-source attestation is silently accepted; trust shifts from "verified" to "operational".

**Owner**: nazarov (registry), framework-operations (review cadence).

---

## 8. Counter-examples — Phase 1 proposals that violate one or more invariants

We name the proposal, name the invariant violated, and give the formal-grounds argument. We are fair: we name the proposal, then state why.

### Counter-example 1: "pending_recv coordinate" — partial fail of DS1

**Proposals affected**: feynman (`own_settled / own_inflight` 7-coordinate split), sbl (`inflight` 7th coordinate, signed). These authors *attempt* to preserve DS1 by defining `own_economic = own_settled + own_inflight`.

**Why partial-fail**: the design *can* be made to satisfy DS1 *if* the valuation function reads `own_economic` rather than `own_settled`. But the re-routing breaks the "one number, one read" simplicity that DS1 is supposed to preserve. Every margin computation, every risk aggregation, every regulatory report would need to know to read `own_economic = own_settled + own_inflight`. C12 (`PositionState[(w, u_MA)]` collapse) and the §13 graceful-degeneration property forbid this: a coordinate must pass the physical-action test (v10.3 §13.2) and be load-bearing on its own.

**The decisive question**: does `pending_recv` (or `own_inflight`) have a *physical action* that is not also a write to `own`? The answer depends on whether we treat custody-confirmation as a physical action distinct from economic ownership. **feynman and sbl say yes**; others (geohot, jane_street, formalis, lattner, halmos, cartan) say no.

**Formal status**: not strictly a violation, but a stronger architectural commitment. The Pareto-arbiter (forthcoming) must decide. **Our recommendation**: reject the seventh coordinate; carry the obligation in L_15 with a status overlay (formalis Phase 1, jane_street, lattner, halmos, cartan convergence).

### Counter-example 2: "reverse on fail" — full violation of DS1 + DS7

**Proposals affected**: none of the 20 propose this. It is a strawman that every author (formalis Phase 1 §8 Counter-Example 2, jane_street §3.5, ashworth §3.1, geohot §6 F1, halmos §6.1) explicitly rejects.

**Why violates**: DS1 (economic exposure existed) + DS7 (failure non-reversal) + IFRS 9.B3.1.3 (regular-way trades not derecognised) + FAQ Q5 + BCBS 239 traceability.

**Formal status**: rejected unanimously across Phase 1.

### Counter-example 3: "single open-window object" — partial violation of StatesHome 3-map

**Proposals affected**: a strawman. ashworth §1.3 considers and rejects a "single open-window object". finops §1.3 considers and rejects a single global "settlement queue" wallet.

**Why violates**: StatesHome §3 ruling (three maps, not four), C12 (`W`-sector collapse), and the §13 reasoning that no new sector is justified unless it carries a discipline distinct from the existing three.

**Formal status**: rejected unanimously.

### Counter-example 4: "settle the cash leg at T, defer the securities leg" — violation of DS18

**Proposals affected**: a strawman; no author actually proposes splitting DvP. Listed for completeness.

**Why violates**: DvP atomicity (DS18) — the conservation argument splits across two transactions, atomicity P2 is broken, there exists a state where cash has moved but securities have not.

**Formal status**: rejected.

### Counter-example 5: "obligation not registered until status change" — violation of DS-Liveness

**Proposals affected**: a strawman; no author proposes deferring obligation registration.

**Why violates**: DS-Liveness requires the obligation to exist as soon as a deadline can elapse. If the trade is committed at $T$ but no obligation row exists, an infrastructure failure between commit and instruction would leave a trade with no liveness guarantee.

**Formal status**: rejected. Per Principle 13.5 (Obligation Completeness), the lifecycle function for the trade event must produce the obligation in its output.

### Counter-example 6: "InFlight stored, not computed" — violation of physical-action test

**Proposals affected**: feynman / sbl explicitly. (karpathy §5 stores per-counterparty PS_payable / PS_receivable, but these are wallets — distinct discipline.)

**Why violates**: §13.1.4 (Definition of `avail` as projection): coordinates pass the physical-action test; projections do not. `InFlight` is fully determined by the obligation log + status flags. Storing it would create a cache that can drift out of sync with the determining state.

**Formal status**: rejected for `inflight` as a coordinate; permitted as a per-(wallet, unit) projection over $L_{15}$. **The Pareto-arbiter must rule.**

### Counter-example 7: "settle by inference (no witness)" — violation of DS4

**Proposals affected**: implicit in geohot's minimalism — he says "if a `sese.025` arrives, status flips." nazarov's INV-DS-2 is the formal corrective: no FSM transition without verified envelope.

**Why violates**: DS4 (no discharge without witness). Allowing operators or schedulers to stamp `Discharged` without an attested envelope is the silent-fallback failure mode.

**Formal status**: this is a strengthening, not a violation in geohot's narrow scope. nazarov's stricter formulation is canonical. **The Settlement Team must enforce DS4 at the FSM level.**

### Counter-example 8: "Herstatt eliminated by ledger design" — false claim

**Proposals affected**: none claim this. Listed because it's the natural temptation.

**Why false**: Herstatt risk is a real-world timing risk that no ledger design can eliminate (v10.3 §2.6). The framework *represents* the asymmetric leg states (DS10), *names* the window, and *quantifies* the exposure. CLS / PvP infrastructure mitigates externally.

**Formal status**: every proposal correctly disclaims elimination; framework-wide acknowledgement.

---

## 9. Proof obligations imposed on the Settlement Team

Each obligation is enumerated and named to a Settlement Team member. The format: `PO-N: [proposer] must show that [property] holds because [reason]`.

### PO-1 — finops: PS_payable / PS_receivable conservation under daily aggregation

**finops** must show that the per-(wallet, counterparty, currency) PS_payable / PS_receivable wallets satisfy DS3 (reconciliation identity) and DS6 (idempotency under duplicate confirmations) under daily aggregation, including netting across counterparties on the morning recon report. The current §3.4 morning-recon formula must be expressed as a deterministic projection over the move stream + obligation log; any "reconciliation engineer's intuition" is insufficient.

**Reason**: finops carries the operational-finance section. The recon identity DS3 is the load-bearing check that ledger leads custody by exactly InFlight; if the per-counterparty grain breaks under aggregation, the morning recon is opaque.

### PO-2 — sbl: late-discharge race policy entry for SETTLEMENT obligation kind

**sbl** must verify (via `VersionPinSidecar` lookup) that the saga compensation tower's policy table has an explicit `SETTLEMENT` entry with the policy `cancel-compensation if not externalised; otherwise queue-and-reconcile`. correctness B-Q-2 (Phase 1) flagged this as inferred, not confirmed.

**Reason**: sbl carries the SBL-composition section, which is where late-discharge most often arises (recall during the open window). Without an explicit policy entry, replay determinism (DS5) is contingent.

### PO-3 — sbl: pin the sign convention on DS3 reconciliation identity

**sbl** must pin the sign convention on DS3 / P29 — the framework-wide reconciliation identity. Phase 1 §10 of sbl explicitly notes the sign-convention issue is open. The convention must be stated such that:
1. The receive-obligation is on the side of the *receiver* (per finops, karpathy, matthias) or the *obligor* (per sbl §1.1), not silently both.
2. The identity reduces to v10.3 line 3538 SBL form when applied to lendable units.
3. Property tests over generated trade streams (testcommittee §3.3 generators) confirm the identity holds at every checkpoint.

**Reason**: DS3 is the most-cited reconciliation identity in Phase 1 (seven independent authors converge on the same algebra modulo sign). Pinning the sign convention is required before the property test can be written.

### PO-4 — matthias: discharge predicates as bitemporal-state-functions, not snapshots

**matthias** must show that all $L_{15}$ discharge predicates of kind `SettlementInstructionDelivery` are expressed as bitemporal-state-functions, not closed-over snapshot values. Concretely: a property test introducing a 2-for-1 stock split between obligation registration ($T$) and obligation deadline ($t_d$) must observe that the discharge fires correctly with the post-split target quantity (200 shares, not 100).

**Reason**: matthias carries the CDM cross-walk and the L_15 obligation-as-CDM-extension PR. G3 in the gap list. Without bitemporal-state-functions, corporate-actions-in-window break DS-Liveness for fungibility-breaking actions.

### PO-5 — isda: closed sum on CSDR failure-type enumeration

**isda** must produce a normalised CSD-failure-reason closed sum, with documented mapping from each CSD's enum (DTC, Euroclear, Clearstream, T2S), and a defined `OTHER → ESCALATE_HUMAN` sink. Pin per `ledger_data_v1.0` §3 versioning algebra.

**Reason**: isda carries the regulatory-mapping section. G1 in the gap list. Without closed sum, DS9 (buy-in compensation closure) and hence DS-Liveness are contingent on manual fallback.

### PO-6 — ashworth: per-jurisdiction manufactured-payment specification

**ashworth** must specify, per jurisdiction (US, EU, UK, JP), the rule for manufactured payments on cum-dividend trades whose record date falls inside $(T, t_d]$. The seller's manufactured-payment obligation must be a separate L_15 row (`obligation_kind = MANUFACTURED_DIVIDEND`), with its own deadline and discharge witness.

**Reason**: ashworth carries the audit-and-IFRS section. G11 in the gap list. The manufactured-payment is a high-frequency error-source that auditors test; without per-jurisdiction codification, ashworth's IFRS 9.B3.2.13 (transfer of contractual rights) claim is incomplete.

### PO-7 — minsky: pin the type-vs-runtime decomposition table for §5

**minsky** must produce the canonical mapping from each invariant (DS1–DS18) to (compile-time | runtime | hybrid), with explicit phantom-typing scope (which units carry which phantom tags), and the cost-benefit assessment of the typing investment per minsky §9.4. The Settlement Team must accept or reject minsky's recommendation: take the typing cost for DS17 + DS7, leave DS1 hybrid, leave the others runtime.

**Reason**: minsky carries the type-theoretic design. The decomposition is decisive for implementation: an over-typed system is an unmaintainable refactor; an under-typed system silently violates DS17 and DS7. The Settlement Team needs a pinned answer.

### PO-8 — testcommittee: TLA+ model check at $|\mathcal{W}|=3, |U|=2, \text{depth}=8$

**testcommittee** must implement the TLA+ model per testcommittee §8.5 and run TLC at $|\mathcal{W}|=3, |U|=2, \text{depth}=8$ with all 18 invariants encoded. Required to pass before the deferred-settlement specification is considered formally verified. State-space size is estimated at $10^5$–$10^6$ states; tractable in minutes on a workstation.

**Reason**: testcommittee carries the test-and-verification section. The TLA+ check is the only mechanism that proves liveness counterexamples are absent in the joint state space.

### PO-9 — testcommittee + temporal: pin the partial-fill recursion bound $D_{\max}$

**testcommittee + temporal** jointly must pin $D_{\max}$, the maximum recursion depth of partial → buy-in → partial → buy-in cascades. jane_street §6 caps at 2; sbl/temporal/karpathy allow recursion. The Settlement Team needs a numeric $D_{\max}$ and a property-test that beyond $D_{\max}$ the cascade transitions to `Defaulted` rather than continuing.

**Reason**: DS11 termination depends on a finite recursion bound. Without one, DS-Liveness is contingent.

### PO-10 — temporal: signal-driven workflow with bounded-set dedup, not heartbeating activity

**temporal** must confirm that `SettlementSaga` is implemented as a signal-driven workflow with timer (per temporal §7.2), *not* as a long-running heartbeating activity. The dedup set (`processed_signals`) must be bounded (n=4096, TTL=30 days per temporal §7.2). The `tx_id` derivation must not include `run_id` or any ContinueAsNew-ephemeral field.

**Reason**: heartbeating a 24-hour activity is the canonical anti-pattern; replay determinism (DS5) breaks under ContinueAsNew if `tx_id` includes ephemeral identifiers.

---

## 10. What we reject from Phase 1 proposals on formal grounds

We name and explain. The Settlement Team must rule on each.

### Reject 1: feynman / sbl — adding a 7th coordinate to the position vector

**Reason**: fails the physical-action test (v10.3 §13.2). `inflight` has no physical action that is not also a write to `own` plus a status update on the obligation. Adding a stored coordinate creates a cache that can drift out of sync with the determining state (DS counter-example 6). The obligation log + status overlay carries strictly more information than a coordinate scalar (per-instruction grain vs aggregate).

**What we accept from feynman/sbl**: the *projection* `inflight(w, u, t) = Σ over open obligations` is correct and useful. It should be a query, not a stored field.

### Reject 2: karpathy / finops / matthias — per-(counterparty, currency) PS wallets as mandatory

**Reason**: the per-counterparty grain is operationally useful but not architecturally mandatory. The reconciliation identity DS3 holds at any aggregation level. Per-instruction wallets (sbl §1.5, temporal) and per-counterparty wallets (karpathy / finops / matthias) are both valid; the Settlement Team must decide based on operational cost (more wallet identities ↔ finer grain).

**What we accept**: at *some* level of aggregation, the wallets must exist as virtual wallets in the closed system (v10.3 §2.5). The contra of every InFlight entry must close to zero somewhere.

**Pareto note**: per-instruction is more granular but cardinality scales with $O(\text{open instructions})$. Per-counterparty is coarser but may collapse to single counterparty. Recommendation: per-counterparty + per-instruction as separate views, both projections over the same obligation log.

### Reject 3: noether / halmos / cartan — promoting the obligation to a unit `u_so` in $\mathcal{U}$

**Reason**: this works mathematically (clean conservation, clean redemption homomorphism) but adds a unit-class that does not pass the StatesHome ruling's minimality test. The obligation already lives in L_15; making it a unit duplicates state and creates a new sector (`obligation_units`) without distinct discipline. The conservation argument (Q(u_so) = 0 by issuance pair) is elegant but the L_15 row carries the same information.

**What we accept from noether/halmos/cartan**: the *redemption-equivalence* invariant (noether N3) — the deferred claim's price tracks the underlying — is exactly DS1 expressed as a price function. The conservation lifting argument (cartan §5.3) is the same as the StatesHome C2 structural argument. **We adopt the proof structure, reject the unit-class proliferation.**

### Reject 4: sbl §6.4 — manufactured-dividend payment is a redirect through the broker virtual

**Reason**: the four-move pattern in sbl §7.4 (`issuer → broker; broker → broker; broker → Alice`) introduces a redundant intermediate step (broker self-write). The cleaner pattern is two transactions: (i) issuer-to-seller cash flow via standard CA; (ii) manufactured-dividend obligation registered as separate L_15 row, discharged seller→buyer.

**What we accept**: the underlying principle (economic owner at $r$ is entitled, regardless of custody) is correct.

### Reject 5: isda §1.2 — inflight virtual wallet between portfolio and counterparty as the load-bearing mechanism

**Reason**: isda's `w_csd_inflight[CSD, omnibus, book]` is an architectural choice; it conflicts with karpathy's per-(real, virtual_cpty) wallet topology and with sbl's per-instruction wallet. The Settlement Team must decide on one mechanism. **We accept the principle that the obligation must close to zero in *some* virtual wallet; we reject the specific mechanism without further argument.**

### Reject 6: jane_street §6 — cap obligation tree depth at 2

**Reason**: this is engineering pragma, not formal ground. The depth bound prevents a known operational pathology (counterparty broken, recursion goes deep) but is not derivable from the invariant register. We *accept* a bound (PO-9) but reject the specific value of 2 without the Settlement Team's explicit decision and supporting property test.

### Reject 7: nazarov §4.2 — single-source escape requires registered authority assumption

**Reason**: this is operational hygiene, not formal ground. The trust-assumption registry (TA-DS-1 through TA-DS-10) is good practice but is not part of the invariant register. We *accept* the gap (G12) but the registry maintenance is operational, not a proof obligation.

### Reject 8: temporal §11 — `gate_settlement_buyin_window_v2` versioning

**Reason**: this is an implementation detail (Temporal's `GetVersion`), not a formal ground for the deferred-settlement specification. The versioning discipline is correct but the gate naming convention is internal to the workflow framework.

---

## 11. Conclusion — the canonical settlement-team commitment

The Settlement Team's deferred-settlement specification is committed to:

1. **The invariant register DS1–DS18** (§1) as the canonical set of properties the implementation must satisfy.
2. **The totality and termination arguments** (§2) for the six top-level workflows.
3. **The DS-Liveness theorem** (§3) — every open obligation reaches a terminal state in bounded time, contingent on G1 (closed-sum failure types) and G8 (cluster availability).
4. **The DS-Replay theorem** (§4) — replay determinism on out-of-order finality, contingent on G2 (UTI discipline) and G5 (restated confirmations).
5. **The type-vs-runtime decomposition** (§5) — 6 compile-time, 9 runtime, 3 hybrid out of 18, with the recommendation to invest in compile-time enforcement of DS17 (capability scoping) and DS7 (failure non-reversal).
6. **The state-space cardinality** (§6) — TLC-tractable at $|\mathcal{W}|=3, |U|=2, \text{depth}=8$ with $\sim 10^5$–$10^6$ states.
7. **The honest gap list G1–G12** (§7) — twelve genuine open obligations that the framework cannot discharge without further constraints. Five (G1, G2, G3, G4, G5) are within scope to close in Phase 2; four (G8, G10, G6, G7) require operational or external constraints; three (G9, G11, G12) are documentation / registry tasks.
8. **The proof obligations PO-1 through PO-10** (§9) — one per Settlement Team member, with named property and named owner.
9. **The rejections** (§10) — eight Phase 1 proposals named and rejected on formal grounds, with the principle accepted and the implementation choice deferred to Pareto arbitration.

Six properties (PO-1, PO-2, PO-3, PO-4, PO-5, PO-9) are real proof obligations the framework must discharge before this design is sound. Two (G8, G10) are operational, not provable. The remaining four gaps (G1, G6, G7, G11, G12) are specification gaps closable by committing to a closed sum, a typing rule, or a property-based test.

None of the gaps is a design defect. Each is a specification gap that can be closed by committing to a closed sum, a typing rule, a registry, or a property-based test.

The deferred-settlement specification is implementation-ready. The invariant register is the test the proposal must pass. We have written it in a form that does not depend on the architectural variants Phase 1 diverged on; the Pareto-arbiter can adjudicate the variants without invalidating any invariant.

— FORMALIS, Phase 2 Settlement Team, 2026-04-30. R. Delloye agent harness.
