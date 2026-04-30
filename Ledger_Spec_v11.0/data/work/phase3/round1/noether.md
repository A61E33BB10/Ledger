# Phase 3 Round 1 — NOETHER adversarial review of `proposal_v1.md`

**Reviewer.** NOETHER (independent; symmetries → conservation laws).
**Target.** `/home/renaud/A61E33BB10/Ledger_Spec_v11.0/data/work/phase2/proposal_v1.md`.
**Posture.** Adversarial. I have read the proposal end-to-end and drilled into `formalis.md §6` (theorems), `correctness.md §3` (49-cell fault matrix and the "seven fault classes"), and the Phase-1 silent-violator register I produced.

> *If a system is invariant under transformation S, a conserved current J follows. If the proposal preserves S in its discourse but does not pin the data carrier of S, the current J is silently lost.*

The proposal's deepest weakness is that **it names the leaves but does not, in any single place, list the carriers of the master symmetries S1–S12 of the Ledger**. As a result, several silent conservation violators from my Phase 1 register survive into the Phase 2 synthesis without being assigned a leaf or an invariant.

---

## §1. Headline grade

**Grade: C+ (UNMITIGATED MAJOR class present; Conservation Lifting does not compose under the proposed seven-fault matrix as stated).**

Justification. The proposal is structurally sound at the leaf level, but five of the twelve master symmetries are silently un-carried, the Conservation Lifting theorem (FORMALIS Theorem 1) does not compose under three of CORRECTNESS's seven fault classes (mis-attributed, silent-corruption, partition), and the Time / Clock authority — the carrier of S3 (time-translation) — is **not a leaf** of NAZAROV's 24. A C+ reflects "the spine is right and the integration is honest, but the proposal cannot yet be defended on adversarial Phase-3 grounds without the corrections below."

| Severity | Count |
|----------|------:|
| BLOCKING | 4 |
| UNMITIGATED MAJOR | 6 |
| MINOR | 5 |

---

## §2. BLOCKING findings

### B1 — Time / Clock authority is not a data leaf (S3 carrier missing)

**Section.** §2.1 (24 leaves), §3.6 (C6 provenance), §6 (realism budget).
**Defect.** The Ledger relies pervasively on S3 (time-translation invariance of contractual rules) and S4 (replay invariance under checkpointing). Both require an **authoritative clock and a canonical now()** whose readings are themselves bitemporally-pinned data. The proposal carries:
- `t_obs`, `t_known` everywhere (good).
- L19 Snapshot, L21 VersionPin (good).
- L22 HashChainAnchor (good).

But **no leaf carries the timestamping authority itself.** Where does `t_known` come from? Whose clock? Under what NTP/PTP/atomic source? Under what leap-second policy? Whose signed assertion attests it? Section §3.6 puts L18 (identity keys), L19 (snapshot), L22 (hash anchor) — but the *clock* is silently delegated to "the executor", which is L24 Orchestration State, which the proposal has just labelled "replay-substrate only; not economic data" (§3.6, V11 reconciliation).

This is structurally identical to a multiplier that is not on ProductTerms: every value carries a `t_known` whose meaning depends on a quantity that has no home and no version pin.

**Conservation consequence.** S3 (time-translation) and S4 (replay invariance) both have no carrier. Calendar-version pinning (L4) is correctly bitemporal, but a clock skew of 2s near a daily-fix boundary moves a fixing into the prior business day silently — `Σ_w` holds, value invariance breaks. This is the canonical Noetherian failure: **the symmetry is preserved in the prose, the carrier is not pinned, the current J leaks.**

**Required mitigation.** Add a leaf — call it `L25 ClockAuthority` or fold into L21 explicitly — carrying `(authority_id, source_kind ∈ {NTP, PTP, GNSS, atomic}, leap_second_policy_version, attested_offset, attestor_signature, t_known)`. Every `t_obs` and `t_known` must reference it. This is the only S3 carrier that is honest.

### B2 — Conservation Lifting (FORMALIS Theorem 1) does not compose under three of the seven CORRECTNESS fault classes

**Section.** §8 (compositional theorems), §5 (49-cell matrix referenced by reference).
**Defect.** FORMALIS Theorem 1 has hypotheses (D-CONS, E-ATOM, D-IDX). It composes cleanly under fault classes {missing, late, duplicated, contradicted}, because each of these is a violation of D-CONS or D-IDX that the executor's commit gate rejects, and atomicity ensures the rejection is total. **It does not compose under {mis-attributed, silent-corruption, partition}**:

1. **Mis-attributed** (e.g., a dividend posted to wallet w′ instead of w with the same `+amount` cancellation in some virtual offset wallet). D-CONS is satisfied locally (`Σ_w Δw(u) = 0`), D-IDX is satisfied (both wallets registered). The handler structurally balances. But the *true* Noether current — wallet-relabelling invariance S1 — is **broken in semantics, satisfied in syntax**. The lifted theorem says nothing about this case because its premise is structural, not semantic.
2. **Silent-corruption.** A wrong multiplier (my Phase-1 canonical violator) corrupts every `accumulated_cost` move by the same factor. `Σ_w` still equals zero. D-CONS holds. The theorem lifts a *vacuous* conservation. Section §3.1 acknowledges this for futures; **§8 does not**.
3. **Partition.** When the executor cannot reach the wallet registry (network partition between executor and StatesHome), atomicity becomes a CAP-style choice: refuse-with-block or proceed-with-stale-cache. E-ATOM as stated does not specify which; if "proceed-with-stale-cache" is ever taken, conservation lifts vacuously over the cache, not over the live ledger.

**Required mitigation.** Theorem 1 must add explicit hypotheses (D-SEMANTIC: handler-class type-tags align with the *intended* wallet semantics, witnessed by capability scopes L23; D-INVARIANT-MASS: a non-vacuous mass scalar exists per unit class — e.g., notional × multiplier — that no single handler can scale uniformly; D-PARTITION: under partition, executor blocks rather than proceeds). Without these three, the lifted conclusion is weaker than the prose claims.

### B3 — Manufactured-dividend rate, locate-haircut convention, and FX-snapshot consistency are silent violators with no named leaf

**Section.** §3.4 (L11 Lifecycle/Oracle), §3.6 (L19 Snapshot), §7 (CDM gaps).
**Defect.** My Phase-1 register (sections 3.5, 3.6) flagged:
- **Manufactured-dividend rate** in SBL (P14 income equivalence) — silent if the manufactured rate is sourced from a different snapshot than the declaration. Proposal §3.4 L11 lists "ManufacturedPaymentRate" as **Missing** in CDM and routes it as "lifecycle attestation". This **does not pin the snapshot** that the manufactured rate must derive from.
- **Locate-haircut convention** — silent because every locate event has its own implicit haircut convention; if these vary across cascade-recall chains, the SBL six-coordinate vector (L9) breaks `own + onloan = const` per entity over a cascade, even though each link satisfies it locally.
- **FX-snapshot consistency.** S7 covariance (currency rescaling) holds **only if all FX rates used in a given V_t come from the same L19 snapshot**. The proposal's L19 is content-addressed, but §3.4 L13 CalibratedMarketObject and §3.5 L15 ValuationRecord both depend on `input_snapshot_id`. **Nothing in the proposal forbids a single ValuationRecord from drawing FX from snapshot A and rates from snapshot B**, so long as both are valid. This is the classic FX-leg/rates-leg snapshot mismatch: each leg internally consistent, S7 broken across legs.

**Required mitigation.** Add the following invariants to FORMALIS L9 / L15:
- `ValuationRecord.snapshot_input` is **scalar, not a set** — exactly one snapshot per record.
- All FX, rate, vol curves consumed by a single valuation are subscripts of that one snapshot.
- ManufacturedPaymentRate (L11 sub-leaf) carries `derived_from_snapshot_id` and a **same-snapshot constraint** with the declaration's L11 attestation.
- Locate-haircut convention is pinned per cascade-recall chain (not per locate).

### B4 — Holiday-calendar bitemporal mode is asserted but not specified, and §3.1 L4 admits it is "awkward"

**Section.** §3.1 L4 (Calendar/Convention), §9.5 (TEMPORAL awkward fits).
**Defect.** The proposal says calendars are "U1, U2 + C-A3" (append-only + bitemporal + vendor honesty) and the Temporal section calls retroactive amendments the "worst fit." **But there are at least three distinct bitemporal modes** for a holiday-calendar amendment, and the proposal does not pick:
1. **Pin-at-deal-time** (calendar version frozen with ProductTerms; later amendments do not retroactively re-resolve schedules).
2. **Pin-at-projection-time** (calendar version frozen with snapshot; replay re-resolves to the calendar version active at snapshot time).
3. **Pin-at-now** (calendar version is the authority's current published version; replay produces today's interpretation).

These are non-equivalent. Mode 1 is the only mode under which S3 (time-translation invariance of contractual rules) holds. Modes 2 and 3 break S3. **The proposal asserts S3-style replay determinism (Property 6) but does not commit to mode 1.** TEMPORAL §6.1 (referenced from §9.5) flags this as awkward but does not resolve it.

**Required mitigation.** Pick mode 1, encode it in L1 ProductTerms as `calendar_version_pin` (a hash of the calendar version active at deal time), and forbid amendments from changing already-pinned schedules. Calendar republication produces a new bitemporal record but does **not** invalidate prior pins.

---

## §3. UNMITIGATED MAJOR findings

### M1 — LEI restatement breaks S1 (wallet-relabelling invariance) on aggregation

**Section.** §3.1 L3, §3.4 L12.
A merged/restated LEI changes the party-key without changing economic substance. If a wallet hierarchy aggregates by LEI, the restatement silently **changes the equivalence classes of S1**: balances that once aggregated under LEI₁ now aggregate under LEI₂. The proposal cites "bitemporal restatement supported" but does not specify whether reports as-of-old must use LEI₁ or LEI₂. Aggregation under bitemporal LEI mapping must be **homomorphic** (Principle 6: f(a+b) = f(a)+f(b)); the proposal does not guarantee this.

**Mitigation.** Specify aggregation behaviour: as-of `t_known` reports use the LEI valid at `t_known`; as-of-now reports use the current LEI; the equivalence is by deterministic LEI-history join, not silent overwrite.

### M2 — Post-hoc Q/R Kalman edits are unmodelled (S11 carrier ambiguous)

**Section.** §3.4 L13, §8 Theorem 5.
A late vendor correction changes the historical innovation residual ν_t. If Q/R are re-fitted on the corrected sequence, the certified posterior changes. S11 (innovation-gating symmetry) requires that the **gating decision at certification time** be reproducible. The proposal makes L13 append-only (good) but does not say whether **Q/R themselves are versioned** or whether re-fitting is a *new* CalibratedMarketObject (correct) or a mutation (forbidden).

**Mitigation.** Q and R are inputs to the calibrator; treat them as elements of L21 VersionPin or as an explicit `CalibrationParameterPin` sub-leaf. A re-fit produces a new L13 record; the prior is preserved.

### M3 — V13 ("no Trade/Position/PnL/Risk/Account table") collides with the homomorphism property (S8)

**Section.** §1.2 V13, §8 Theorem 4 (Substantiation).
S8 is the forgetful homomorphism F: CDM → Ledger preserving composition. Theorem 4 (Substantiation) says every report is a projection π_Q(D₁..D₆). For this to be a homomorphism (Principle 6), π must satisfy π(a + b) = π(a) + π(b) under the relevant operation. **The proposal does not prove that "balance" as a derived view is additive in the move stream.** If the projection includes any non-additive operation (e.g., max, last, conditional rebooking), Theorem 4 is unsafe.

**Mitigation.** Restrict π_Q to the additive monoid of the StatesHome carrier. Non-additive aggregations (max-drawdown, HWM) must be carried as state in L9 PositionState explicitly, not as projections.

### M4 — S2 (permutation invariance of independent moves within a transaction) is asserted but not enforced

**Section.** §3.5 L14.
"Transaction ≈ NonEmpty<Move> with conservation refinement" — but the conservation refinement is `Σ Δ = 0`. **It does not assert order-independence.** If two moves within a single transaction have a non-commuting effect (e.g., one closes a wallet, the other writes to it), the transaction is order-dependent. The proposal does not require Move composition to be commutative.

**Mitigation.** Either require Moves within a Transaction to be **disjoint by (wallet, unit, field)** (forces commutativity), or remove the S2 claim from the symmetry register.

### M5 — Conservation Lifting under partition (BLOCKING B2 #3) cross-cuts §6 C-A8 (closed-system boundary integrity)

**Section.** §6 C-A8.
C-A8 is "closed-system boundary integrity, owned by the Architecture review board." This is too thin. Partition between executor and StatesHome is a **realistic operational fault** addressed in CORRECTNESS Cluster VII; C-A8 ducks it as an architectural posture. The realism budget should distinguish **temporary partitions** (CAP-style) from **permanent ones** (architectural).

**Mitigation.** Split C-A8 into C-A8a (no out-of-system economic data) and C-A8b (executor↔StatesHome partition refuses-rather-than-proceeds, with a named SLA on partition resolution).

### M6 — Single-coordinate Move (S9, SBL) is asserted as L9 PositionState invariant but not checked at the executor commit gate

**Section.** §3.3 L9, §8 Theorem 1.
The six-coordinate vector `(own, onloan, borr, coll_post, coll_recv, coll_rehyp)` per-(wallet, unit) is a `MINSKY` type-level constraint and a `FORMALIS` invariant. The executor commit gate (E-ATOM, E-COMMIT) is described as "atomicity + referential integrity + conservation" — **but does it enforce single-coordinate?** A multi-coordinate move would satisfy `Σ_w = 0` while violating S9. The proposal is silent.

**Mitigation.** Add to E-COMMIT explicitly: every committed Move touches **exactly one** coordinate of one (wallet, unit) per entity.

---

## §4. MINOR findings

### m1 — V14 ("per-regulator obligation kinds") is correct but understated

The proposal honours my preference for "obligation is uniform; regulator is a tag", which preserves the regulator-relabelling symmetry. However the proposal does not name this as a **symmetry** anywhere. Add S13: regulator-tag symmetry to the master register.

### m2 — Provenance edges (C6 §3.6) form a category, not just metadata

GROTHENDIECK Pass B notes C6 is the morphism-recording layer. The proposal states this once and moves on. The **composition law** (provenance edges compose: provenance(A→B) ∘ provenance(B→C) = provenance(A→C) up to canonical iso) should be an explicit invariant on L17. This is a 1-categorical Noetherian property: ascending chains of provenance terminate.

### m3 — §6 unconditional U3 (deterministic identity) does not say which canonicalisation

`hash(canonical_serialise(payload))` — but two different canonical-serialise functions are non-commensurable. Pin the canonical-serialise version under L21.

### m4 — §9.4 surrogate strategy for L8 (replay determinism under cosmic-ray bit flips) is fine but does not pin the erasure-coding parameters

The surrogate "content-addressing + erasure coding + cross-replica verification" needs a Reed-Solomon `(n, k)` choice that survives the worst observed bit-flip rate. This is an empirical parameter; pin it in L7 Policy and version it.

### m5 — §5 49-cell matrix has no "type-prevented" tag

CORRECTNESS notes some cells are type-prevented (zero-frequency). A Goodhart trap forms here: a cell that is "type-prevented" today may not be tomorrow if a refactor weakens the type. Tag each cell with the **specific type-level invariant** that prevents it, so a future change to that type relights the cell.

---

## §5. Summary verdict

**Inner ground for the grade.** The proposal is structurally honest and surfaces its disagreements (§9). Every leaf has a home, every theorem has hypotheses. But the synthesis falls short of Noetherian discipline at three places:

1. The **symmetry register is not in the document.** Without S1–S12 on a page next to the 24 leaves, no reviewer can check that every symmetry has a carrier. (The proposal would benefit from a §2.4 "symmetry-to-leaf carrier matrix.")
2. **Conservation Lifting (Theorem 1) is structural; the seven CORRECTNESS fault classes include three semantic ones (mis-attributed, silent-corruption, partition) that the theorem's hypotheses do not cover.** The lifted conclusion is weaker than the prose suggests.
3. **Time / Clock authority is the unfilled hole.** S3 has no carrier. Pin it.

Until B1–B4 are addressed, the proposal cannot be defended on the grounds claimed. With those four fixed and M1–M6 mitigated, the grade rises to A−.

> *"One should reveal the inner ground for equality."* The inner ground for the proposal's claim of replay determinism is a clock authority that does not yet exist as a leaf. Pin it, and the symmetries follow.

— end of NOETHER Phase 3 Round 1 review —
