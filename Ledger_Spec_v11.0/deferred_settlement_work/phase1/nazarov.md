# Deferred Settlement: A Data-Boundary Specification

**Author:** NAZAROV — Data Layer Architect
**Phase:** 1 (independent proposal, no cross-talk)
**Target:** `deferredSettlement.tex`
**Date:** 2026-04-30
**Stance:** zero-trust at the boundary; settlement finality is an external observation, not an inference.

---

## 0. Boundary statement (read this first)

The gap between trade time `T` and settlement time `T+2` is **not** a gap inside the closed system. It is a gap in **what the closed system has been told by external attestors** about the state of the world at the CSD/custodian boundary. The Ledger has perfect knowledge of the trade (an internal event); it has zero knowledge of settlement finality until a CSD or custodian message crosses the boundary, is signature-verified, deduplicated, snapshotted, and admitted as an `L_10 LifecycleOracle` (or `L_11 ExternalConfirmation`) record.

Therefore the question "how does the Ledger represent the open settlement obligation" decomposes into three orthogonal sub-questions:

1. **Internal economic state** — what does the position vector `(own, onloan, borr, coll_post, coll_recv, coll_rehyp)` look like during the window? (representation question; mostly settled by v10.3 §SBL and the StatesHome ruling.)
2. **External observation discipline** — by what attestation mechanism does "the trade settled" or "the trade failed" become a fact admissible to the ledger? (the NAZAROV question; this proposal.)
3. **Obligation lifecycle FSM** — how does the `L_15 Obligation` record transition from `Pending → Discharged | Compensated | Defaulted`, and what observation triggers each transition? (mostly settled by `ledger_data_v1.0` §L_15; this proposal pins the *observations* that drive the FSM.)

Sub-question (1) is owned by the Ledger architect. Sub-question (3) is owned by the Obligation specifier. **Sub-question (2) is mine, and the entire failure surface of T+2 settlement lives there.** Anything that says "the trade settled" without naming the attestor, the envelope, the snapshot, the dedup key, the freshness bound, and the failure mode is a hole in the closed-system invariant.

---

## 1. State representation

### 1.1 Three concurrent representations during `[T, T+2]`

A buy of 100 XYZ at $50 on T (cash-equity, US, T+2 regime — adapt to T+1 in §1.5):

| Object                      | Home                                              | At T                                              | At T+2⁻                              | At T+2⁺ (settled)                            |
|-----------------------------|---------------------------------------------------|---------------------------------------------------|--------------------------------------|-----------------------------------------------|
| Economic position           | `L_6 PositionState[w_us, u_XYZ].own`              | `+100`                                            | `+100`                               | `+100` (unchanged)                            |
| Custody position            | `L_6 PositionState[w_us, u_XYZ].own_at_custody`   | `+0`                                              | `+0`                                 | `+100`                                        |
| Cash receivable             | `L_15 Obligation[id].kind = CashLeg(USD,−5000)`   | `Pending(due=T+2)`                                | `Pending(due=T+2)`                   | `Discharged(witness=sese.025@T+2)`            |
| Securities receivable       | `L_15 Obligation[id].kind = SecLeg(XYZ,+100)`     | `Pending(due=T+2)`                                | `Pending(due=T+2)`                   | `Discharged(witness=sese.025@T+2)`            |
| Counterparty virtual wallet | `L_6 PositionState[w_cpty_virtual, u_XYZ].own`    | `−100`                                            | `−100`                               | `−100`                                        |

The economic position `own` moves at `T`, *not* at `T+2`. This is non-negotiable: PnL is recognised at trade time per the v10.3 valuation theorem (`V_t = Σ_u own(u)·P_t(u)`), so any representation that delays `own` to `T+2` would silently de-recognise economic exposure during the window.

The novel coordinate is `own_at_custody` — the projection that custodian/CSD statements are reconciled against. **This is not a new state coordinate**; it is a *witnessed projection* of `own` reduced by the set of obligations whose witness has not yet arrived:

```
own_at_custody(w, u) := own(w, u) − Σ { qty(o) : o ∈ open_obligations(w, u), o.kind = SecLeg(u, +qty) }
                                + Σ { qty(o) : o ∈ open_obligations(w, u), o.kind = SecLeg(u, −qty) }
```

This projection is *computed on read*, like `avail` in the SBL six-vector. It carries no independent state and cannot drift from `own ⊕ open_obligations`.

### 1.2 The Obligation as the carrier of the gap

The state of the gap lives entirely in `L_15 Obligation` — one record per leg per trade. An obligation carries:

- `obligation_id` (content-addressed: `hash_jcs(trade_id, leg_kind, attempt_seq)`)
- `kind ∈ {SecLeg(u, qty), CashLeg(ccy, amt)}` (closed sum)
- `counterparty` (LEI, virtual wallet ref)
- `due_t` (T+2 23:59:59 venue time, or the venue-specific cutoff from `L_4 CalendarConvention`)
- `dvp_pair_id` (the obligation_id of the matched leg, if DvP)
- `fsm_state ∈ {Pending, AwaitingFinality, PartiallyDischarged, Discharged, Failed_CSDR, Compensated, Defaulted}` (closed sum, no ellipsis)
- `discharge_witness: Option<L_10_Ref ⊕ L_11_Ref>` (a pointer to the lifecycle event or external confirmation that proved discharge)
- `corrections_chain: List<L_10_Ref>` (later attestations restating earlier ones; bitemporal)

**The fsm_state is a function of the witness set, not a separate writable field.** This is the single most important constraint in this proposal: an operator cannot stamp `Discharged` without a discharge_witness; the system cannot compute `Discharged` without one either. State is *driven by attested observations*, never by inference, never by "we assume it settled because the deadline passed."

### 1.3 What is *not* state

- "Settled" as a free-standing flag — it is the FSM state derived from witnesses.
- Time-since-trade — derivable from `T` and `now()`.
- Estimated settlement probability — outside scope; this is a risk-engine computation, not data-layer state.
- Counterparty intent — not observable, not admissible.

### 1.4 Composition with v10.3 internal mechanics

- **Short selling (§13).** A short sale at T creates a `Pending SecLeg(u, −qty)` obligation; `own` becomes negative at T. The position vector's `own < 0` is exactly the "unsettled short" state. SBL borrow to cover (§GPM): a separate borrow transaction adjusts `borr`, but the original obligation is what discharges at T+2 against the buyer.
- **Recall.** A recall in the SBL workflow generates its own obligation chain (`L_15`) bounded by the recall window in `L_4`. Composition with deferred settlement is by *separate obligation_ids*; never overlay-merge.
- **Corporate action in `[T, T+2]`.** The record-date attestation (`L_10.CorporateAction`) is a *separate* lifecycle observation that adjusts the cum/ex flag on the unit. Whether the buyer or seller is entitled to the dividend depends on whether settlement *finalised* before record date — i.e., on the discharge_witness timestamp, not the trade timestamp. **This is the single most common silent-bug class in cash equities settlement: inferring entitlement from `T` instead of from the discharge_witness `t_obs`.** §6.3 below is dedicated to this.
- **Cross-currency / Herstatt.** Two `CashLeg` obligations in different currencies, settling on different CSD/payment systems with non-overlapping operating hours. Each leg has its own discharge_witness from its own attestor. CLS (Continuous Linked Settlement) provides PvP within its window; outside CLS, the gap between leg-1-settled and leg-2-settled is the Herstatt window. The data-layer treatment: **the trade is one transaction; settlement finality is two independent observations**; the Herstatt window is the time difference between the two `t_obs` values on the discharge_witnesses.
- **DvP atomicity.** Inside the CSD, DvP is atomic — a single `sese.025` carries both legs of a DvP pair as a single settled event. Outside the CSD (e.g., FoP delivery vs separate cash payment), DvP atomicity is *not* guaranteed by the CSD; it is reconstructed from two independent witnesses, and the gap between them is a real risk. The `dvp_pair_id` field allows the data layer to check that both legs share a discharge_witness with identical `t_obs` (atomic case) or to flag the gap (non-atomic case) as a `BreakRegister L_18` event.

### 1.5 T+1 (US post-2024)

Identical structure with `due_t = T+1 23:59:59 venue time`. The DTCC affirmation cutoff (9pm ET on T) becomes a *pre-finality milestone* — itself an attested observation (DTCC ITP CTM affirmation message), but **affirmation is not finality**. Conflating affirmation with discharge has been a recurring error in T+1 implementations and is forbidden by the closed-sum FSM (`Pending` and `AwaitingFinality` are distinct states, neither equals `Discharged`).

---

## 2. Move sequence with conservation

### 2.1 The four moments

```
T           — trade execution, internal event, instant
T+1 9pm ET  — DTCC affirmation cutoff (T+1 regime; first attested external milestone)
T+2⁻        — strictly before settlement finality
T+2 (cutoff)— CSD batch cutoff; finality posted by CSD
T+2⁺        — strictly after settlement finality (or fail)
T+2 + n     — restatement / correction window (CSDR penalty fires; partial settle catch-up; corrections)
```

### 2.2 Move-stream content at each moment

| Moment      | `L_13 MoveStream` content (this trade only)                                                                                                                                  | Source attestor                                                                       | Conservation check                                                |
|-------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------|-------------------------------------------------------------------|
| `T`         | `BalancedTx { Move(w_us, w_cpty_v, u_XYZ, +100), Move(w_cpty_v, w_us, u_USD, −5000) }` plus `OpenObligation(SecLeg, +100, due=T+2)` and `OpenObligation(CashLeg, −5000, due=T+2)` | Internal trading system (signed by trader auth)                                       | ∑ moves = 0 per unit per class (own, USD)                         |
| `T+1 9pm`   | `Affirmation` event admitted from DTCC ITP CTM (a `L_11 ExternalConfirmation`); does *not* mutate `own`                                                                     | DTCC (LEI: 254900-DTCC-…), signed wire                                                | Vacuous (no balance move); affirmation = pre-finality attestation |
| `T+2⁻`      | (no entry — until external attestor posts)                                                                                                                                   | n/a                                                                                   | n/a                                                               |
| `T+2 cutoff`| `DischargeObligation(obligation_id, witness=sese.025@T+2, t_obs=T+2_15:30:00)` — twice, once per leg of the DvP pair                                                          | CSD (DTCC for US, Euroclear/Clearstream for EU); signed sese.025 or MT54x             | ∑ obligation deltas per (w, u) collapses correctly to 0           |
| `T+2 + n`   | (a) restatement: previous discharge_witness corrected → bitemporal new row in `L_10`, no rewrite; (b) custodian-confirms via camt.053; (c) CSDR penalty fires → new obligation | CSD (correction); custodian (MT535/MT536); penalty regime authority                 | All corrections are new bitemporal rows, never mutations          |

### 2.3 Conservation property during the window

The Ledger conservation law `Σ_w w(u) = 0` holds **at every moment** — *because* the trade is recorded as a balanced transaction at T with the counterparty's virtual wallet absorbing the `−100`. The discharge at T+2 is **not a balance move** in the position vector; it is an FSM transition on `L_15 Obligation` that flips `discharge_witness` from `None` to `Some(sese.025_ref)`. **No double-counting risk** because there is no second `own +100` movement at T+2.

What the discharge does change: `own_at_custody` (the read-time projection) re-evaluates because the open-obligation set shrinks. This is observed by the custodian-reconciliation activity, not by a state mutation.

### 2.4 The replay invariant

For a fixed event sequence `E = [trade@T, affirm@T+1, sese.025@T+2]`, replaying `E` produces a bit-identical state. **What if the messages arrive out of order?** They will. `sese.025` may arrive before `affirm` (DTCC may post finality before the affirmation event has even propagated through ITP). The data layer must therefore enforce:

- **Per-message bitemporal `(t_obs, t_known)`** so that "affirmation observed at T+1 9pm but only known at T+2 9am" is a first-class, queryable fact.
- **Idempotency-on-replay (`N_4`)** so that re-presenting the same `sese.025` does not double-discharge.
- **Order-independent FSM transition function** so that `discharge(obligation, witness)` is associative and commutative on the witness set, not sequential.

The third point matters: the FSM is best modelled not as a sequence of transitions, but as a **lattice** where the state is `f(witness_set)` and witnesses can arrive in any order. Then "replay determinism" reduces to "f is a pure function of the witness set", which is mechanically checkable.

---

## 3. Invariants

These are mandatory; an implementation that violates any of them is unsafe.

### 3.1 INV-DS-1 — Economic exposure at T (MANDATORY)

**Statement.** The portfolio value `V_t` for `t ∈ [T, T+2]` is computed using `own(w, u)` as it stands at `T`, not as it stands at custody.

**Formally.**
```
∀ t ∈ [T, T+2):  V_t = Σ_u own(w, u) · P_t(u)
```
where `own(w, u)` reflects the trade made at T regardless of whether the trade has settled at the CSD.

**Why.** Path-independent PnL (v10.3 §4.3) requires that economic recognition happen at trade time. Recognising at settlement time would (a) silently delay PnL by 1–2 days, (b) make PnL a function of CSD batch timing (a non-economic variable), (c) violate the lifecycle-value-invariance theorem on T+1 trades that span a corporate-action ex-date. This is non-negotiable.

**Test.** Property: trade at T with price P(T)=p₀; market moves to P(T+1)=p₁; PnL between T and T+1 = `100 · (p₁ − p₀)`, *independent* of whether settlement has occurred at T+1.

### 3.2 INV-DS-2 — No discharge without witness

**Statement.** No obligation transitions to `Discharged | PartiallyDischarged | Compensated` without a discharge_witness pointing to a verified `L_10` or `L_11` record.

**Formally.**
```
∀ o ∈ Obligation:  o.fsm_state ∈ {Discharged, PartiallyDischarged, Compensated}
                    ⟹ o.discharge_witness ≠ None
                    ∧ verify_envelope(o.discharge_witness) = true
```

**Why.** The FSM state is the closed-system claim that the external world has confirmed something. Allowing operators or schedulers to stamp "discharged" without a witness is the silent-fallback failure mode and is forbidden.

### 3.3 INV-DS-3 — No fail-by-inference

**Statement.** The transition `Pending → Failed_CSDR` requires a *positive attestation* of fail, not the mere absence of a discharge attestation past `due_t`.

**Formally.**
```
o.fsm_state = Failed_CSDR ⟹ ∃ a ∈ L_10 :
   a.kind = SettlementFail ∧ a.obligation_ref = o.obligation_id
   ∧ verify_envelope(a) = true
```

**Why.** "Absence of finality" is a treacherous category — it can mean (a) the trade failed, (b) the CSD message is delayed, (c) the gateway is down, (d) we are looking at the wrong feed, (e) the attestor's clock is wrong. Inferring `Failed` from any of these is a security-equivalent bug. We require a positive attestation (CSD-issued fail status, or a custodian's positive non-receipt confirmation) to transition. The "absence" case is `AwaitingFinality`, not `Failed`.

### 3.4 INV-DS-4 — Snapshot determinism on replay

**Statement.** Given the same multiset of attested envelopes (regardless of arrival order), replay produces a bit-identical `L_15 Obligation` set.

**Formally.**
```
fold(Obligation, witness_multiset_A) ≡ fold(Obligation, witness_multiset_B)
   when witness_multiset_A = witness_multiset_B (as multisets)
```

**Why.** Time-travel and IFRS 13 audit reconstruction require that "what we knew" at any historical time `t_known` is bit-identical regardless of replay path. This is the standard determinism boundary `B_4` (External event oracles: signal-driven, snapshot-pinned).

### 3.5 INV-DS-5 — Bitemporal restatement, never mutation

**Statement.** When a CSD or custodian issues a correction (e.g., "the sese.025 we sent at T+2_15:30 was wrong; please use this restated sese.025"), the original record is not deleted or overwritten. A new bitemporal row is appended with `t_known = now()` and `t_obs = T+2_15:30:00`. The corrections_chain on the obligation grows by one.

**Why.** Two query modes are first-class: `as_of(t_known)` (what we knew at the moment) and `with_corrections_through(t_known')` (best estimate now of truth at `t_obs`). Mutation collapses these. (`N_9`, `Definition bitemporal modes` from `ledger_data_v1.0`.)

### 3.6 INV-DS-6 — Counterparty-side conservation under fail

**Statement.** If `o.fsm_state = Failed_CSDR`, the counterparty virtual wallet retains the dual obligation; both sides of the unmatched trade carry symmetric unresolved positions until the next observation (buy-in, mutual cancel, court adjudication) closes them.

**Why.** Fails are not symmetric in attribution but are symmetric in conservation. The Ledger never "absorbs" a fail by adjusting `own` silently.

### 3.7 INV-DS-7 — Witness key-integrity

**Statement.** Every discharge_witness must verify against the attestor's *active public key as known at `t_obs`*, fetched from `L_19 ClockAuthority + key registry` bitemporal entry.

**Why.** Key rotation is real. A `sese.025` issued on T+2 must be verified against the CSD's signing key valid on T+2, not against today's key. ADR-11 in `ledger_data_v1.0` makes public verification keys append-only precisely so historical envelopes remain re-verifiable (boundary `B_11`).

---

## 4. Reconciliation lead-lag

### 4.1 The three lead-lag regimes

| Regime           | Lead source                       | Lag source                       | Lead-lag tolerance        |
|------------------|-----------------------------------|----------------------------------|---------------------------|
| **CSD-led**      | DTCC sese.025 (US T+1)            | Custodian MT535/MT536 (next day) | 0–1 business day          |
| **Custodian-led**| Custodian intraday SLATE          | CSD end-of-day                   | up to several hours       |
| **Counterparty-led** | Counterparty back-office FpML | CSD batch                        | up to T+2 + N             |

### 4.2 The aggregation protocol (per leaf `L_10` / `L_11`)

For an obligation `o` matched to a DvP pair, finality may be attested by **up to four independent attestors** for the *same* settlement event:

1. **Primary** — the CSD itself (DTCC, Euroclear, Clearstream) via sese.025 / MT54x.
2. **Secondary** — our custodian (the bank holding our omnibus account at the CSD), via MT535/MT536 daily statement.
3. **Tertiary** — the counterparty's back-office, via an FpML/CDM trade-state notification.
4. **Quaternary** — the CCP (if cleared), via end-of-day clearing report.

**Aggregation rule (default).** `Discharged` requires:
- CSD attestation (primary), OR
- Custodian attestation + counterparty confirmation (2-of-2 quorum from secondary + tertiary)

**Rationale.** The CSD is the single point of legal settlement finality (per CSD Regulation Article 39). We accept a 2-of-2 quorum among next-best sources as a fallback, but **never** a single non-primary attestor. Single-source escape is permitted *only* with a registered authority assumption (`N_8.2`) — and our authority assumption registry must list which counterparties / custodians qualify and which do not, with named owner.

**Disagreement.** If sources disagree (e.g., CSD says Discharged; custodian says Failed), the obligation goes to `BreakRegister L_18` with a `wf-settlement-disagreement` workflow handle. The fsm state is **not** advanced silently to either claim. The `L_18` FSM resolves the break with four-eyes operator + audit trail, ultimately producing a *new* attestation that becomes the discharge_witness (e.g., a manual-resolution `L_10` with attestor = internal-operator-LEI and a registered trust assumption).

### 4.3 Freshness contract

| Source               | Max staleness                | Update trigger    | Behaviour at boundary                          |
|----------------------|------------------------------|-------------------|------------------------------------------------|
| DTCC sese.025        | 30 min from CSD batch close  | Push (event)      | At threshold: emit `wf-confirm-break`, do not infer fail |
| Custodian MT535      | T+1 09:00 venue time         | Push (daily)      | At threshold: poll/pull; second threshold = break  |
| Counterparty FpML    | T+2 12:00 venue time         | Push (per change) | At threshold: bilateral exception query          |
| CCP EOD report       | T+1 06:00 venue time         | Push (daily)      | At threshold: escalate to CCP operations          |

Clock skew across attestors is bounded by `L_19 ClockAuthority`. Any `t_obs` arriving with skew > `L_7^Pb.clock_skew_tolerance` (TBD-by-Operations, suggested 5 seconds) is admitted to `L_10` but *flagged* and excluded from quorum until reconciled.

---

## 5. CDM cross-walk

### 5.1 What CDM 6.0.0 gives us directly

| Concept                                | CDM type                                            | Status                                          |
|----------------------------------------|-----------------------------------------------------|-------------------------------------------------|
| Trade execution                        | `BusinessEvent` with `intent = ExecutionIntent`     | **Direct**                                      |
| Settlement intent (DvP pair)           | `Transfer` with `settlementType = DeliveryVersusPayment` | **Direct**                                  |
| Observation of settlement              | `ObservationEvent` extends `BusinessEvent`          | **Partial** — CDM models lifecycle observations but does not natively carry the `sese.025` attestation envelope; we extend with `attestation_envelope` field |
| Obligation lifecycle                   | (none directly)                                     | **Missing** — CDM has `Transfer.transferStatus` but no first-class obligation FSM type. Our `L_15 Obligation` fills the gap. |
| External settlement message            | (none directly)                                     | **Missing** — CDM does not import ISO 20022 sese.025 / sese.023 / camt.053. The `L_11 ExternalConfirmation` leaf carries the inbound mapping. |

### 5.2 Concretely

- `L_10.SettlementFinality` (proposed new lifecycle constructor, complementary to existing 18 in `L_10`) maps onto CDM `BusinessEvent { intent: SettlementIntent, after.transferStatus: Settled, attestation_envelope: <sese.025_envelope> }`.
- `L_10.SettlementFail` maps onto `BusinessEvent { intent: SettlementIntent, after.transferStatus: Failed, fail_reason: <CSDR reason code>, attestation_envelope: <CSD fail-status envelope> }`.
- `L_15 Obligation` is Ledger-native; its FSM extends what CDM exposes. Phase-2 work item: propose a CDM PR adding `Transfer.lifecycleObligation` with the same closed-sum state.

---

## 6. Failure modes (named, scoped, attested)

### 6.1 The fail (CSDR)

**Observation source.** CSD-issued status report (sese.024 status with `MatchingStatus = NMAT` or `PendingFailingReason ≠ null`), or a daily settlement-fail register feed from the CSD.

**Attestation envelope.** Identical to discharge: signed by CSD, timestamped against `L_19`, content-hashed, deduplicated by (settlement_instruction_id, status_seq).

**FSM transition.** `Pending → Failed_CSDR` requires an `L_10.SettlementFail` admitted to the snapshot and bound by `obligation_ref`.

**CSDR penalty obligation.** On `Failed_CSDR`, a *new* obligation `L_15` is created of `kind = CSDR_PENALTY` per `ledger_data_v1.0` §1383 — schema `(rate_basis_points, days, source_lei, currency)`. Its lifecycle is independent.

**Buy-in trigger.** A buy-in observation (`L_10.BuyIn`) creates a chain of new obligations replacing the failed one; the original obligation transitions to `Compensated` with discharge_witness = the buy-in event.

### 6.2 Partial settlement

**Observation source.** CSD-issued partial-settle confirmation: `sese.025` with `PartialSettlement = true`, `SettledAmount < InstructedAmount`.

**FSM transition.** `Pending → PartiallyDischarged`. The remaining quantity creates a *child obligation* with `parent_obligation_id`, `kind = SecLeg(u, +remaining_qty)`, `due_t = original_due_t + 1bd`.

**Conservation.** The original obligation's `qty` is split into two records summing exactly to the parent. Audit-reconstructable.

### 6.3 Corporate action in `[T, T+2]` — the cum/ex trap

This is the most common silent-bug class.

**Scenario.** Buy on T; ex-dividend date is T+1; settlement on T+2 (or T+1 in T+1 regime).

**The trap.** The buyer at T owns the trade economically from T (per INV-DS-1) and is therefore "cum" (entitled to the dividend). But the *registered holder* on the dividend record date is determined by the CSD's books — and if settlement has not finalised by the record date, the seller is the registered holder. The dividend posts to the seller's CSD account; a *manufactured payment* must flow buyer → seller? No — *seller → buyer* via the counterparty back-office (the seller has received cash that is economically owed to the buyer).

**The data-layer requirement.**

1. **Cum/ex determination is itself an attested observation.** `L_10.CorporateAction { event_type: DividendCum, ex_date, record_date, payment_date }` from the issuer/index admin or corporate-action provider (a multi-source `N_8` aggregation: typically Bloomberg + Refinitiv + Clearstream).
2. **Entitlement at record date is computed from `own_at_custody(w, u, t = record_date)` from the CSD's perspective**, not from `own(w, u, t = record_date)` (the Ledger's economic view).
3. **The manufactured-payment obligation is a *separate* `L_15` record** with `kind = ManufacturedDividend(amt)`, distinct from the original SecLeg/CashLeg obligations.
4. The trust-assumption registry must record: "the corporate-action data provider's ex-date attestation is treated as authoritative; if it's wrong, manufactured payments are computed wrong and the buyer is shorted/over-paid the dividend." Owner: corporate-actions operations.

### 6.4 Reconciliation breaks

**Definition.** A break is a *positive* observation that two attestors disagree about a settlement event, or that an expected attestation has not arrived within its freshness window.

**Routing.** All breaks become `L_18 BreakRegister` records with workflow handles `wf-settlement-disagreement | wf-confirm-late | wf-amount-mismatch | wf-quantity-mismatch`. The FSM in `L_18` (per `ledger_data_v1.0` §operational-fsm) governs resolution.

**No silent inference.** A break does not advance the obligation's FSM. Resolution produces an attested artefact (operator-signed `L_10` with named trust assumption, or a counterparty-issued correction) that does.

### 6.5 Cross-currency Herstatt window

Two `CashLeg` obligations on different currency rails; each settles on a separate payment system with separate hours. The "settled" state of the trade as a whole is `(leg1_state, leg2_state)`. The data-layer treatment:

- Two independent discharge_witnesses, one per leg.
- The `dvp_pair_id` (here `pvp_pair_id`) links them for reconciliation.
- `t_obs` deltas across legs measure the Herstatt window directly.
- A "fully PvP-settled" state requires both witnesses; absence of one is `AwaitingFinality` on that leg, *not* an inferred fail.

CLS-eligible trades carry a CLS attestation envelope as a *third* witness asserting atomic PvP within the CLS window. CLS attestation has its own attestor identity, its own signing key, its own freshness contract.

---

## 7. Worked example — the canonical case

### 7.1 Setup

- `T`: buy 100 XYZ at $50, US cash equity, T+2 regime (use 2024 to keep `T+2`; mutatis mutandis for T+1).
- Buyer's wallet: `w_us`; counterparty: `cpty` (LEI `5493...CPTY`); counterparty virtual wallet: `w_cpty_v`.
- CSD: DTCC (LEI `254900-DTCC-...`).
- At `T+1`: market mid = $52.

### 7.2 Move stream and obligation lifecycle

**At T (trade execution, internal event):**

```
L_13 BalancedTransaction tx_T:
  Move(w_us, w_cpty_v, u_XYZ, +100)   // Ledger gains 100 XYZ from cpty virtual
  Move(w_cpty_v, w_us, u_USD, +5000)  // ... balanced by 5000 USD owed to cpty
  // ∑ per unit per class = 0 ✓

L_15 Obligation o_sec:
  kind = SecLeg(u_XYZ, +100)
  due_t = T+2 23:59 venue
  fsm_state = Pending
  discharge_witness = None
  dvp_pair_id = o_cash.id

L_15 Obligation o_cash:
  kind = CashLeg(USD, −5000)
  due_t = T+2 23:59 venue
  fsm_state = Pending
  discharge_witness = None
  dvp_pair_id = o_sec.id
```

**At T+1 (market move; valuation):**

```
own(w_us, u_XYZ) = +100  (unchanged from T)
P_{T+1}(u_XYZ) = 52
V_{T+1}(w_us) = 100 · 52 + cash_balance_unchanged_for_this_position
PnL(T → T+1) for this trade = 100 · (52 − 50) = +$200  ✓
```

**No cash has moved. INV-DS-1 holds.**

**At T+2 (settlement finality):**

DTCC posts a `sese.025` for the matched DvP pair.

```
Inbound L_11 ExternalConfirmation:
  message_id = "DTCC-SESE025-20260502-000123"
  attestor = DTCC LEI
  signature = <DTCC-signed envelope>
  t_obs = 2026-05-04T15:30:00Z (DTCC batch finality)
  t_known = 2026-05-04T15:30:42Z (gateway ingest)
  payload (ISO 20022 sese.025):
    SettlementInstrId = "...123"
    SettlementStatus = Settled
    SettledQuantity = 100 XYZ
    SettledAmount = 5000 USD
    PaymentReceived = true
  envelope_verifies_against_DTCC_pubkey_active_at_t_obs = true ✓

Synthesised L_10 LifecycleEvent ev_finality:
  constructor = SettlementFinality (proposed extension, NS-PR-...)
  obligation_refs = [o_sec.id, o_cash.id]
  attested_by_envelope = <ref to L_11 record above>
  t_obs = 2026-05-04T15:30:00Z

FSM transition (atomic StateDelta per StatesHome C3):
  o_sec.fsm_state: Pending → Discharged
  o_sec.discharge_witness = ev_finality.id
  o_cash.fsm_state: Pending → Discharged
  o_cash.discharge_witness = ev_finality.id
  // Both legs share the same witness — DvP atomicity preserved
  
own_at_custody(w_us, u_XYZ) at t_known = 2026-05-04T15:30:42Z:
  = own − Σ open_obligations
  = 100 − 0  // sec leg now discharged
  = 100  ✓ (matches DTCC's posted balance)
```

**Conservation check:** No moves to `L_13` are emitted at T+2 by the discharge; the entire settlement-finality observation is a state delta on `L_15` with attestation. `Σ_w w(u_XYZ) = 0` continues to hold throughout.

**PnL audit:** PnL between T and T+2⁺ is fully explained by the price path of `u_XYZ`; no settlement-timing artefact appears.

### 7.3 Variant — the fail

If at T+2 the DTCC instead posts:

```
L_11.payload (sese.024 status):
  SettlementStatus = Failed
  PendingFailingReason = "INSU" (insufficient securities)

→ Synthesised L_10.SettlementFail bound to o_sec.id
→ o_sec.fsm_state: Pending → Failed_CSDR
→ A new L_15 Obligation o_csdr_penalty is created with
   kind = CSDR_PENALTY, parent_obligation = o_sec.id
→ wf-buy-in workflow triggers per CSDR Article 7
```

`own(w_us, u_XYZ)` is still `+100` (the trade is still recognised economically). `own_at_custody` is `0` (DTCC has not delivered). The discrepancy is a *visible*, *attested* break — not silent.

### 7.4 Variant — the corrections chain

T+3 morning: DTCC issues a correction stating yesterday's `sese.025` had wrong `SettledAmount` ($4,995 not $5,000):

```
Inbound L_11 ExternalConfirmation:
  message_id = "DTCC-SESE025-20260505-000456"
  payload.CorrectionOf = "DTCC-SESE025-20260502-000123"
  payload.SettledAmount = 4995

Bitemporal action:
  - Original L_11 row preserved (t_obs = T+2 15:30, t_known = T+2 15:30:42).
  - New L_11 row appended (t_obs = T+2 15:30, t_known = T+3 09:14:00).
  - o_cash.corrections_chain += new ev_finality_v2.id
  - "as_of(T+2 18:00)" still returns SettledAmount = 5000 (what we knew then).
  - "with_corrections_through(T+3 12:00)" returns SettledAmount = 4995.
  - A reconciliation break L_18 fires for the $5 discrepancy → wf-amount-mismatch.
```

**Both query modes are first-class.** Audit can replay either the contemporaneous or the corrected view.

---

## 8. Trust assumption registry (deferred-settlement subset)

Each item: name, scope, owner, violation consequence, detection signal.

| TA-#       | Statement                                                                                  | Owner                          | Violation consequence                                          | Detection signal                                          |
|------------|--------------------------------------------------------------------------------------------|--------------------------------|----------------------------------------------------------------|-----------------------------------------------------------|
| TA-DS-1    | The CSD's signing key (e.g., DTCC) is uncompromised at `t_obs`                            | CSO + identity-and-trust ops   | Forged settlement finality; double-spend of cash leg            | Out-of-band CSD verification heartbeat; PKI revocation feed |
| TA-DS-2    | The CSD does not equivocate (publish two contradictory `sese.025` for the same instr)     | Operations + Audit             | Disagreement between primary and secondary witnesses            | Cross-source consistency check on every finality event    |
| TA-DS-3    | Custodian's daily MT535 reflects the same CSD state we observe                             | Custodian-relationship owner   | Reconciliation break on T+1 morning                             | Daily reconciliation diff > tolerance                     |
| TA-DS-4    | ISO 20022 schema versions in inbound messages match our pinned mapper version              | Data-engineering boundary owner| Silent field misinterpretation; wrong amount/quantity            | Schema version pin mismatch detected at ingress           |
| TA-DS-5    | The corporate-action provider's ex-date attestation is the canonical ex-date              | Corporate-actions operations   | Manufactured-payment computation wrong; over/under-payment       | Cross-source CA disagreement (Bloomberg vs Refinitiv vs CSD) |
| TA-DS-6    | `L_19 ClockAuthority` time skew across attestors is within tolerance                      | Time-source operations         | Cross-attestor `t_obs` ordering ambiguous; wrong corrections-chain | NTP/PTP drift monitor exceeding `L_7^Pb.clock_skew_tolerance` |
| TA-DS-7    | DTCC's "Failed" status genuinely represents non-settlement, not "delayed but settling"     | Operations + CSD-relationship  | Premature CSDR penalty creation; needless buy-ins                | Late-arriving Discharged event after Failed declared      |
| TA-DS-8    | The counterparty's virtual-wallet identity (LEI + account suffix) is correctly mapped     | Onboarding + identity-and-trust| Settlement attributed to wrong counterparty; conservation breaks | LEI verification at trade time (against L_3 PartyLEI)    |
| TA-DS-9    | CLS attestation, when present, does mean atomic PvP within CLS window                     | FX operations                  | Hidden Herstatt risk on assumed-atomic CLS leg                  | CLS-leg `t_obs` delta > 0 detected                         |
| TA-DS-10   | Single-source escape (only one of {CSD, custodian, counterparty} attests) is documented   | Operations leadership          | Silent acceptance of unverifiable finality                       | Quorum-violation audit log; quarterly review              |

**Untyped trust forbidden.** Anything in the deferred-settlement window that is not cryptographically attested *must* be in this registry with a named owner and a detection signal, or it is a security hole.

---

## 9. Threat model

| Attacker class                             | Capability                                                                              | Mitigation                                                                                                          | Residual risk                                                                            |
|--------------------------------------------|-----------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------|
| Malicious vendor (CSD message tampering)   | Forge `sese.025` payload; no signature                                                  | `N_2` envelope verification; CSD pubkey rotation; pinned key registry                                              | Insider at CSD with key access                                                           |
| Malicious gateway (our ingestion side)     | Drop, replay, or alter messages between wire and snapshot store                          | Gateway-side signature verification at the wire; content-addressed snapshot store; cross-replica hash comparison    | Compromise of the gateway signing key (TA-DS-4 partially)                                |
| Malicious operator (internal)              | Force-stamp `Discharged` without witness; force-stamp `Failed` to trigger penalty       | INV-DS-2 / INV-DS-3 enforced at type level (FSM transition function takes a witness); four-eyes on manual override | Operator + audit collusion                                                               |
| Malicious counterparty back-office         | Send fake FpML "settled" notifications                                                  | Counterparty FpML is *only* admitted as tertiary; never single-source-discharges                                    | Coordinated attack between counterparty and our custodian (very high cost)               |
| Network adversary                          | Delay, reorder, drop messages                                                           | Bitemporal `(t_obs, t_known)`; idempotency on dedup keys; freshness contracts with observable thresholds            | Sustained DoS exceeding all freshness windows → operations escalation                    |
| Replay attacker                            | Re-present yesterday's `sese.025` today                                                 | Idempotency-key dedup on `message_id + content_hash`; `t_known` strictly monotone per attestor                       | None                                                                                     |
| Equivocating CSD                           | Send conflicting attestations to different participants                                  | Cross-source consistency check; `BreakRegister` on disagreement; out-of-band CSD verification (TA-DS-2)             | CSD is the legal source of truth; equivocation = legal action, not a data-layer recovery |
| Clock-skew adversary                       | Manipulate attestor's clock to misorder corrections                                      | `L_19 ClockAuthority` cross-source consistency; tolerance enforcement at admission                                   | Coordinated multi-attestor clock attack                                                  |
| Forgery via expired key                    | Forge messages signed with a rotated-out CSD key                                         | Bitemporal key registry: verify against the key valid at `t_obs`, not today's key (ADR-11, B_11)                    | Compromise of the historical key while still within attestation window                   |
| Mapping-layer manipulation                 | Submit valid `sese.025` that exploits a mapper bug to mis-discharge a different obligation | Mapping is total, version-pinned, deterministic; replayable bit-identically (`N_11`)                                | Undiscovered mapper bug → property-test fuzz coverage, FRTB-style residuals             |

---

## 10. Verification approach

An auditor confirms a candidate implementation by:

1. **Boundary completeness audit.** Enumerate every code path that mutates `L_15 Obligation.fsm_state` or `o.discharge_witness`. Confirm each is gated by an attested envelope verification or by a `BreakRegister` resolution that itself produced a new attestation. **No path may skip the gate.**

2. **Replay determinism property.** For a corpus of historical settlement event logs, randomly permute the arrival order of envelopes (within their `t_obs` constraints) and confirm bit-identical replay output. Required pass rate: 100%.

3. **Witness-set fold check.** The FSM transition function `step(state, witness_set) → state'` must be a pure function of the witness set, not of arrival order. Property-test with set permutations.

4. **Bitemporal correctness check.** Synthesise correction streams and confirm `as_of(t_known)` returns the contemporaneous view and `with_corrections_through(t_known')` returns the corrected view. Independent first-class results.

5. **Trust-registry coverage check.** Enumerate every untyped-trust path in the codebase (any code that reads external data without verifying a signature). Confirm each appears in the trust registry with a named owner and a detection signal, or remediate.

6. **Threat-model walkthrough.** For each row of §9, exercise the attack path against the test environment; confirm the listed mitigation activates.

7. **Conservation under corrections.** Synthesise restatement streams that retroactively change `SettledQuantity` or `SettledAmount`. Confirm `Σ_w w(u) = 0` holds in *both* `as_of` and `with_corrections_through` views.

8. **Manual-override audit.** Every `L_10` event with `attestor = internal-operator-LEI` (manual resolution) must have a four-eyes audit record and a registered trust-assumption reference.

9. **Key-rotation re-verification.** Replay one-year-old envelopes through the current verifier; confirm they verify against historical keys (and fail against rotated-in keys).

---

## 11. Open items (Phase 2 work)

These are deliberately deferred:

- **Cryptographic primitive ratification.** Signature scheme, hash for content addressing, JCS canonicalisation conformance — flagged for cryptographer ratification.
- **CDM PR for `Transfer.lifecycleObligation`.** Coordinate with the Rosetta/CDM working group; see the existing `attestor_state.md` Rosetta NS1-7 backlog.
- **Manual-resolution attestor LEI.** Each operator LEI used for manual `L_10` synthesis must itself be in `L_3 PartyLEI` with role-tagged authority, and rotation discipline must be specified.
- **Cross-jurisdictional CSDR adaptation.** The CSDR penalty regime applies to EU-CSD-settled trades; US/UK/APAC equivalent regimes have different cutoffs, different penalty bases, different fail-attestation message formats. Phase-2 work item: per-jurisdiction freshness contracts.
- **PvP attestation envelope from CLS.** CLS publishes settlement attestations via a proprietary channel; mapping into our `L_11` envelope format and key registry needs vendor-side specification.
- **The "fail" attestation when the CSD goes silent.** If DTCC is offline at T+2 cutoff, no attestation arrives — neither Settled nor Failed. INV-DS-3 forbids inferring Failed; the obligation stays `AwaitingFinality`. Phase-2 work item: time-bounded escalation policy (24h, 48h, 5d) with explicit operator-attested transitions.

---

## 12. The boundary, restated

Every datum that crosses the trust boundary in deferred settlement — sese.025, MT54x, MT535, FpML notifications, CCP reports, corporate-action notices — must arrive signed, timestamped, deduplicated, and replayable. The Ledger's `own` is recognised at T (internal event, no boundary crossing). The Ledger's claim that the trade has *settled* is admissible only via attested external observations. There is no third option.

The framework's path-independent PnL theorem and its time-travel guarantee survive deferred settlement because the gap is represented as **first-class state** (`L_15 Obligation`) driven by **first-class observations** (`L_10 LifecycleOracle`) crossing **first-class envelopes** (`N_2`). Any implementation that skips an envelope, fakes an observation, or silently advances an obligation FSM converts a closed-system invariant into an institutional trust assumption — and at that point, the ledger has lost its claim to be the system of record.

Hold the boundary. There is no inside if the outside is not named.

— NAZAROV, 2026-04-30
