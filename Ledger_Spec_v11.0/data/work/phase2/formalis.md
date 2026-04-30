# FORMALIS Phase 2: Per-Leaf Invariants, Totality, Termination, Determinism, Compositional Theorems

*Committee: Leroy (Chair), Coquand, Huet, Paulin-Mohring, de Moura, Avigad*

> "A specification without invariants is a wish; a workflow without a termination argument is a prayer; an accessor without a totality story is a partial function pretending to be a theorem. We make all three explicit."
> — Xavier Leroy, opening the Phase 2 deliberation.

## §0 — Stance and Reading Convention

This is the FORMALIS Phase 2 contribution to the Ledger v11.0 data specification. We speak as a **Data Team author**, not as the Phase 3 convergence arbiter (which a fresh FORMALIS instance will perform). We do **not** pre-judge convergence; we structure invariants around the *probable* leaves of the canonical taxonomy that NAZAROV will produce, derived from cross-cutting Phase 1 signal, while keeping our claims tier-axis-label-agnostic where possible.

**Convergence signal across the 19 Phase 1 enumerations.** Independent of taxonomic vocabulary (NAZAROV's six-floor restructure A–F; correctness's eleven categories; grothendieck's three sheaves $\mathcal{F}_{\text{Defn}}$, $\mathcal{F}_{\text{Obs}}$, $\mathcal{F}_{\text{Eff}}$; jane_street's "ProductTerms / Reference / Market.Observable / Market.Calibrated / AttestedObservation / Execution"; halmos's D1–D14; minsky's twelve floors; cartan's eleven sections; isda's expanded floors; finops, feynman, lattner, geohot, karpathy, matthias, sbl, temporal, testcommittee, noether, formalis Phase 1), the **majority of enumerations converge on a 7–11-leaf structure** isomorphic to FORMALIS Phase 1's D1–D10 plus or minus minor regroupings. The differences are mainly in (i) whether to merge raw market data and oracle attestation; (ii) whether to split off "system-emitted attestations" as a primary tier; (iii) whether obligation, workflow-orchestration, capability/identity warrant primary or secondary status; (iv) where calibrated parameters sit. We design Phase 2 invariants so they survive any of the credible Phase 3 groupings.

**Per-leaf labelling.** We use FORMALIS Phase 1's tier-letter notation (D1–D10) as a stable internal handle; the Phase 3 arbiter may relabel. The mapping of D-tiers to "leaves" is one tier ⇒ one or more leaves. Sixteen leaves are addressed below (`L1–L16`), corresponding to a plausible NAZAROV taxonomy; section §6 maps these to the Phase 1 alternative groupings.

**Schema for every leaf.** For each leaf $L_i$ we state, in formal notation:

- **Type invariants** $I^{\text{type}}_{i,j}$ — preserved by every constructor; if all are type-level, we mark "type-level (free)"; otherwise we mark "runtime (must be checked)".
- **Workflow invariants** $I^{\text{wf}}_{i,j}$ — preserved by every state transition reachable from the canonical FSM.
- **Composition invariants** $I^{\text{comp}}_{i,j}$ — preserved when the datum composes with neighbouring data at type interfaces (Identity ↔ Status, Status ↔ State, State ↔ Move, Move ↔ Snapshot, Snapshot ↔ Calibration, etc.).

Typographic convention: $\mathcal{U}$ unit set; $\mathcal{W}$ wallet set; $\mathcal{E}$ entity set; $\mathcal{T}$ time; $\mathbb{D}$ exact decimal; $\Sigma$ event log; $\mathcal{S}$ ledger state. We write `Option[T]`, `NonEmpty[T]`, `Refine[T, P]`, `Map[K, V]`. Predicates as $P, Q$; refinements via subset types $\{x : T \mid P(x)\}$.

---

## §1 — The 16 Probable Leaves

The leaves we address are listed first as an index for cross-reference; FORMALIS's Phase 1 D-tier appears in parentheses.

| # | Leaf | Phase-1 D-tier | Plain English |
|---|---|---|---|
| L1 | `UnitIdentity` (UnitId, ProductTerms versioned) | D1.1, D1.2 | identity & versioned terms |
| L2 | `ReferenceMaster` (instrument, calendar, day-count, taxonomy enums) | D1.3, D1.4, D1.5, D1.7 | external authoritative tables |
| L3 | `LegalAgreement` (ISDA, CSA, GMSLA, mandate, etc.) | D1.6 | legal documents |
| L4 | `Party / LEI / Counterparty` | D10.1 partial + new | legal entity reference |
| L5 | `UnitStatus` (shared mutable per-unit) | D2.1, D2.2 | shared lifecycle |
| L6 | `PositionState` (per-(wallet,unit) scalar projection) | D3.1, D3.3 | per-position experience |
| L7 | `PositionVector` (six-coordinate, generalised under SBL) | D3.2 | position vector under GPM |
| L8 | `RawObservation / OracleAttestation / Snapshot` (raw + signed + bundled) | D4.1–D4.3 | raw + attested observables |
| L9 | `CertifiedCalibration / Jacobian / ValuationRecord` (Kalman posterior + Greeks + price) | D5.1–D5.3 | certified pricing artefacts |
| L10 | `Move / Transaction / StateDelta / CDMBusinessEvent` (the journal) | D6.1–D6.4 | event log |
| L11 | `Derived Projections` (`balance`, `V_t`, `avail`, settlement instruction, regulatory report) | D7.1–D7.5 | regenerable cache |
| L12 | `Obligation / DischargePredicate / CompensationAction` | D8.1–D8.3 | first-class obligations |
| L13 | `WorkflowHistory / ActivityResult / FSMState` | D9.1–D9.3 | Temporal orchestration |
| L14 | `WalletRegistry / Capability / KeyRegistry` | D10.1–D10.3 | actor authorisation |
| L15 | `MarketDataSnapshot` (separated for emphasis as the determinism boundary) | D4.3 (split) | content-addressed bundle |
| L16 | `SmartContractCode / ModelCode (versioned)` | D9 partial + new | versioned executable code as data |

We reserve L17 placeholders for tier additions raised by minsky (firm config, accounting policy), feynman (system schema catalogue, code/model version pins), and finops (firm identity), which the Phase 3 arbiter may merge into L2 or L4 or split out.

---

## §2 — Per-Leaf Invariants

Each leaf carries (T) type invariants, (W) workflow invariants, (C) composition invariants. For each invariant we mark `[type-level]` (free under suitable refinement type or closed sum), `[runtime]` (must be checked at constructor or write), or `[hybrid]` (a refinement type that is constructed via a runtime gate).

### L1 — `UnitIdentity` (UnitId + ProductTerms versioned)

**(T1)** Type invariant — registration injectivity of `UnitId`:
$$\forall u_1, u_2 \in \text{UnitStore}.\; u_1.\text{id} = u_2.\text{id} \implies u_1.\text{terms}_{v_0} = u_2.\text{terms}_{v_0}.$$
`[hybrid]`: closed sum on `UnitKind`; runtime hash-collision check at registration; thereafter type-level.

**(T2)** Type invariant — `NonEmpty` terms versions:
$$\forall u \in \text{RegisteredUnit}.\; \text{ProductTerms}(u) \in \text{NonEmpty}[\text{TermsVersion}].$$
`[type-level]`.

**(T3)** Type invariant — `TermsAmendment` is a closed sum `{Preserving, Breaking}`; the fungibility predicate is part of `ProductTerms` and itself versioned (Ledger StatesHome C8).
`[type-level]`.

**(W1)** Workflow invariant — append-only versioning:
$$\forall u, t_1 \le t_2.\; \text{versions}(u, t_1) \subseteq \text{versions}(u, t_2).$$
`[runtime]` at amendment handler.

**(W2)** Workflow invariant — Preserving/Breaking dichotomy:
$$\text{is\_fungibility\_preserving}(t_{\text{curr}}, t_{\text{new}}) = \text{Breaking} \iff \exists\, u_{\text{new}} \in \mathcal{U}\; \text{with } \text{SupersededBy}(u_{\text{old}} \to u_{\text{new}}).$$
`[runtime]` (predicate must execute at amendment time).

**(C1)** Composition invariant — every `Move`, every `StateDelta`, every `Obligation` references a `RegisteredUnitId`:
$$\forall m \in \Sigma.\; m.\text{unit} \in \text{dom}(\text{UnitStore}).$$
`[hybrid]` — `RegisteredUnitId` refined subtype constructible only after registration; runtime gate at executor.

**(C2)** Composition invariant — `current_terms : RegisteredUnitId \to TermsFields` is total (head exists by `NonEmpty`).
`[type-level]`.

### L2 — `ReferenceMaster` (instrument, calendar, day-count, taxonomy enums)

**(T1)** Type invariant — bitemporal record:
$$\forall r \in \text{ReferenceData}.\; r.\text{vendor\_timestamp} \le r.\text{knowledge\_timestamp}.$$
`[runtime]` at ingestion gate.

**(T2)** Type invariant — `DayCount` is a closed CDM-aligned enum; pure function `(\text{Date}, \text{Date}) \to \mathbb{D}$ for each variant.
`[type-level]`.

**(T3)** Type invariant — `BusinessCalendar` is total over its `effective_range`:
$$\forall c, d.\; d \in c.\text{effective\_range} \implies \text{is\_business\_day}(c, d) \in \{\bot, \top\}.$$
`[type-level]` via refined date pair.

**(T4)** Type invariant — `CDMEnum_*` are closed sums per CDM version; pattern matches must be exhaustive.
`[type-level]` (compiler-checked).

**(W1)** Workflow invariant — monotonicity in vendor time:
$$\forall (s, i, v_1), (s, i, v_2) \in \text{Master}.\; v_1 < v_2 \implies (\text{vendor\_timestamp}(v_1) \le \text{vendor\_timestamp}(v_2)).$$
`[runtime]`.

**(W2)** Workflow invariant — calendars never retroactively delete a holiday already used by a settled event (avoids cash-flow restatement loop):
$$\forall c, d, e \in \Sigma.\; \text{used}(e, c, d) \implies d \in \text{Holidays}(c) \text{ as known at } e.\text{time}.$$
`[runtime]` at calendar amendment handler.

**(C1)** Composition invariant — every `ProductTerms` reference to a `CalendarId` / `DayCount` resolves at registration time:
$$\forall u, t = \text{register\_time}(u).\; \text{ProductTerms}(u, t).\text{calendar\_refs} \subseteq \text{dom}(\text{CalendarRegistry}_t).$$
`[runtime]` at registration gate.

### L3 — `LegalAgreement` (ISDA, CSA, GMSLA, mandate, ...)

**(T1)** Type invariant — every agreement carries a finite, nonzero LEI party set with valid LEIs (D10):
$$|\text{parties}(a)| \ge 1 \land \text{parties}(a) \subseteq \text{ValidLEI}.$$
`[runtime]` at ingestion (LEI registry lookup).

**(T2)** Type invariant — agreement document hash is content-addressed:
$$\forall a.\; a.\text{document\_hash} = \text{SHA256}(a.\text{canonicalised\_document}).$$
`[runtime]` at ingestion.

**(W1)** Workflow invariant — once cited by a loan/mandate, the cited version is frozen for that loan/mandate:
$$\forall u_{\text{loan}}, t.\; \text{cited\_agreement\_version}(u_{\text{loan}}, t) = \text{cited\_agreement\_version}(u_{\text{loan}}, t_0)$$
where $t_0$ is registration time — semantic preservation under amendment.
`[type-level]` via binding the cited version into `ProductTerms[u_loan]`.

**(C1)** Composition invariant — every CSA-bound move references a registered agreement:
$$\forall m \text{ with } m.\text{type} = \text{COLLATERAL}.\; m.\text{csa\_ref} \in \text{dom}(\text{AgreementRegistry}).$$
`[runtime]`.

### L4 — `Party / LEI / Counterparty`

**(T1)** Type invariant — LEI conforms to ISO 17442 (20-char, checksum-valid):
$$\forall \ell \in \text{LEI}.\; \text{format\_valid}(\ell) \land \text{checksum\_valid}(\ell).$$
`[runtime]` at ingestion; thereafter `[type-level]` via refined `ValidLEI`.

**(T2)** Type invariant — entity status is a closed sum `{ACTIVE, LAPSED, RETIRED, MERGED, DUPLICATE, ANNULLED, PENDING_VALIDATION, PENDING_TRANSFER, PENDING_ARCHIVAL}` (NAZAROV §1.1; GLEIF).
`[type-level]`.

**(W1)** Workflow invariant — bitemporal status track:
$$\text{lei\_status\_as\_of}(\ell, t) \text{ defined for all } t \ge \text{first\_known}(\ell).$$
`[runtime]`.

**(C1)** Composition invariant — every move whose source/destination wallet's owner is an external LEI requires `ACTIVE` status at move time (sanctions-style fail-closed):
$$\forall m, w = m.\text{src} \lor m.\text{dst}.\; \text{external}(w) \implies \text{status}(\text{owner}(w), m.\text{time}) = \text{ACTIVE}.$$
`[runtime]` executor gate; required for new bookings, NOT for unwinds of pre-existing positions.

### L5 — `UnitStatus` (shared mutable per-unit)

**(T1)** Type invariant — `lifecycle_stage` is a closed sum; absorbing terminals $\{\text{MATURED, EXPIRED, TERMINATED, SETTLED, CANCELLED, DEFAULTED}\}$ have no outgoing transitions:
$$\forall \sigma \in \text{TerminalSet}.\; \nexists\, e \in \text{Event}.\; \delta(\sigma, e) \ne \sigma.$$
`[type-level]` via refined transition function.

**(T2)** Type invariant — registration-totality (StatesHome C5):
$$\forall u \in \text{RegisteredUnit}.\; \text{UnitStatus}(u) \in \text{Defined}.$$
`[type-level]` via the requirement that the registration handler initialise every field with its typed default.

**(T3)** Type invariant — product-specific status type so illegal field combinations are unrepresentable (Ledger §7.3 line 1045):
The status type is indexed by `UnitKind`; only kind-relevant fields are present.
`[type-level]` (closed sum + dependent-product).

**(W1)** Workflow invariant — single-writer per field (StatesHome C11):
$$\forall f \in \text{StatusFields}, \forall \delta \in \Sigma.\; \delta.\text{field} = f \implies \delta.\text{writer\_handler} = \text{canonical\_writer}(f).$$
`[type-level]` via phantom-typed writer capability; `[runtime]` cross-check at executor commit.

**(W2)** Workflow invariant — lifecycle monotonicity to absorbing terminals (acyclic): the transition graph is a DAG when contracted on {non-terminal → terminal} edges. Equivalently, $\text{lifecycle\_stage}$ never re-enters a non-terminal stage from a terminal.
`[runtime]` at transition handler.

**(C1)** Composition invariant — `IndexNAV` series methodology version is Preserving across the series unless an explicit Breaking event resets a fresh strategy unit:
$$\forall t_1 \le t_2.\; \text{nav}(u, t_1).\text{methodology\_version} \le_{\text{Preserving}} \text{nav}(u, t_2).\text{methodology\_version}.$$
`[runtime]` at IndexNAV publication.

**(C2)** Composition invariant — `superseded_by` link consistent with `ProductTerms` Breaking amendments:
$$\text{superseded\_by}(u_{\text{old}}) = u_{\text{new}} \iff \text{Breaking amendment} \in \text{ProductTerms}(u_{\text{old}}).\text{tail}.$$
`[runtime]` at amendment handler.

### L6 — `PositionState` (per-(wallet,unit) scalar projection)

**(T1)** Type invariant — `PositionState : (\mathcal{W}, \mathcal{U}) \to \text{Option}[T]`; **Some(zero) ≢ None** (StatesHome §2.2):
$$\text{position\_state}(w, u) = \text{Some}(\text{zero}_P) \iff w \text{ has held } u \text{ and closed out};$$
$$\text{position\_state}(w, u) = \text{None} \iff w \text{ has never held } u.$$
`[type-level]` — Option is the accessor type; the storage discipline is monotone-carrier (rows never deleted).

**(T2)** Type invariant — for each field $f$, the type of $f$ is product-indexed: futures `accumulated_cost`, OTC `tradeLifecycle`, mandate `hwm`, etc.; ill-typed fields cannot be combined.
`[type-level]`.

**(W1)** Workflow invariant — single-writer per field (C11), as in L5.W1.
`[type-level]` + `[runtime]`.

**(W2)** Workflow invariant — for each *conserved* field $f$ (per Ledger §15 GPM and §2.4):
$$\forall u, t.\; \sum_{w \in \mathcal{W}} f(\text{position\_state}(w, u, t)) = 0$$
(structural zero-sum, including the vacuous empty-holders base case StatesHome C9).
`[runtime]` at executor commit; per-event-class proof.

**(W3)** Workflow invariant — for each monotone field (e.g., `hwm`):
$$\forall t_1 \le t_2.\; f(\text{position\_state}(w, u, t_1)) \le f(\text{position\_state}(w, u, t_2)).$$
`[runtime]` (refinement type carries proof token but not full proof).

**(C1)** Composition invariant — close-out leaves `Some(zero_P)`, never deletes the row (load-bearing for wash-sale lookback, VM-settle replay, record-date entitlement reconstruction; StatesHome §2.2).
`[runtime]` at close-out handler; storage layer must reject delete-row API on `PositionState`.

**(C2)** Composition invariant — every `StateDelta` whose key references `PositionState` resolves to a `RegisteredUnitId` and a `RegisteredWallet`:
$$\forall \delta.\; \delta.\text{key} = (w, u) \implies w \in \text{dom}(\text{WalletRegistry}) \land u \in \text{dom}(\text{UnitStore}).$$
`[runtime]`.

### L7 — `PositionVector` (six-coordinate, generalised under SBL)

**(T1)** Type invariant — six-coordinate vector over $\mathbb{D}$:
$$\vec{w}_e(u) = (\text{own}, \text{onloan}, \text{borr}, \text{coll\_post}, \text{coll\_recv}, \text{coll\_rehyp}) \in \mathbb{D}^6.$$
For `is_lendable = false` units, only `own` is non-zero (Ledger §15.4 Remark 15.4 graceful degeneration).
`[type-level]` via kind-indexed family that reduces to a scalar variant for non-lendable kinds.

**(T2)** Type invariant — Single-Coordinate Move Principle: every move modifies exactly one coordinate of one unit on two entities.
$$\forall m \in \Sigma_{\text{SBL}}.\; |\{c : c \text{ touched}\}| = 1.$$
`[type-level]` via phantom-typed `Move[Coordinate]`.

**(W1)** Workflow invariant — Proposition 15.7 conservation:
$$\forall u, t.\; \sum_{e \in \mathcal{E}} (\text{own}_e(u) + \text{borr}_e(u) - \text{onloan}_e(u) - \text{coll\_rehyp}_e(u)) = \text{externally\_issued}(u).$$
`[runtime]` at executor commit.

**(W2)** Workflow invariant — borrower over-lending impossibility (Ledger §15.16):
$$\forall e, u.\; \text{onloan}_e(u) \le \text{borr}_e(u) + \text{own}_e(u).$$
`[runtime]` at `lend` and `re-lend` handlers.

**(W3)** Workflow invariant — `coll_post` $\ge 0$, `coll_recv` $\ge 0$, `coll_rehyp` $\le \text{coll\_recv}$.
`[runtime]` at posting / rehypothecation handlers.

**(C1)** Composition invariant — projections `avail`, `possess`, `encumb` are pure functions of the vector and are NEVER stored:
$$\text{avail}(e, u) = \text{own}_e(u) + \text{borr}_e(u) - \text{onloan}_e(u) - \text{coll\_post}_e(u).$$
`[type-level]` — the projections have no storage cell; they are computed on demand (P20 holds by definition not by check).

### L8 — `RawObservation / OracleAttestation / Snapshot`

**(T1)** Type invariant — bitemporal pair refined:
$$\forall o \in \text{RawObservation}.\; o.\text{vendor\_timestamp} \le o.\text{knowledge\_timestamp}.$$
`[hybrid]` — refined record type, runtime check at ingestion.

**(T2)** Type invariant — `ObservableKind` is closed sum (so a swap rate cannot be mis-routed to a vol surface).
`[type-level]`.

**(T3)** Type invariant — `OracleAttestation` adds `signature : Sig`; refined subtype `VerifiedAttestation` constructible only via verifier (Huet's "trust boundary explicit" critique).
`[hybrid]`.

**(T4)** Type invariant — `VendorSnapshot` is content-addressed: `integrity_hash = SHA256(canonical(observations))`.
`[runtime]` at construction.

**(W1)** Workflow invariant — strict append-only:
$$\forall t_1 \le t_2.\; \text{Observations}_{t_1} \subseteq \text{Observations}_{t_2}.$$
`[runtime]` at ingestion gate.

**(W2)** Workflow invariant — restatement appends, never overwrites:
$$\text{restate}(o, o') \implies \text{Observations after} = \text{Observations before} \cup \{o'\} \text{ with } o \text{ retained}.$$
`[runtime]`.

**(W3)** Workflow invariant — fail-closed for sanctions and contractual fixings (NAZAROV CC-1, CC-4 for sanctions data):
absence beyond freshness threshold blocks new-booking workflows.
`[runtime]` at gateway.

**(C1)** Composition invariant — every `CertifiedCalibration` cites its input snapshot, and the snapshot's hash matches:
$$c.\text{snapshot\_input} = s.\text{id} \implies s.\text{integrity\_hash} = \text{SHA256}(\text{canonical}(s.\text{observations})).$$
`[runtime]` on calibration construction.

**(C2)** Composition invariant — every `ValuationRecord` cites `market_data_snap : SnapshotId`; replay-by-snapshot reproduces bit-identical valuation:
$$\text{value}(u, t, m, s) = \text{value}(u, t, m, s) \text{ for all replays of } s.$$
`[runtime]` (replay test); `[type-level]` totality.

### L9 — `CertifiedCalibration / Jacobian / ValuationRecord`

**(T1)** Type invariant — `CertifiedCalibration.state_vector \in \Theta_{AF}` (no-arbitrage admissible region; Valuation §5.6); `covariance` is positive-semi-definite:
$$x_{t|t}^{\text{certified}} \in \Theta_{AF} \quad\land\quad P_{t|t} \succeq 0.$$
`[runtime]` at certification gate; `[type-level]` `Certified[Calibration]` constructible only by certifier.

**(T2)** Type invariant — `Jacobian` is parameterised by `ModelId` so a Heston Jacobian cannot be applied to a Black-Scholes record (model-consistency, Valuation Remark 3.13):
$$j : \text{Jacobian}[m] \implies j.\text{model\_id} = m.$$
`[type-level]`.

**(T3)** Type invariant — `ValuationRecord.dirty_price = clean_price + accrued`:
$$\text{dirty} = \text{clean} + \text{accrued}.$$
`[runtime]` at construction; `[type-level]` via smart constructor.

**(T4)** Type invariant — `Quality` is a closed sum `{FIRM, INDICATIVE, APPROXIMATE, STALE, FAILED}`; refined subtype `FirmRecord` constructible only after PnL-explain pass.
`[type-level]`.

**(W1)** Workflow invariant — certification gate (Valuation §5.7): per-instrument residuals within tolerance, aggregate WRMSE within tolerance, no-arb projection passes.
`[runtime]`.

**(W2)** Workflow invariant — `Quality = FIRM ⟹ fsm_state = Explained`:
$$q(r) = \text{FIRM} \implies \sigma(r) = \text{Explained}.$$
`[type-level]` via FirmRecord refined subtype.

**(C1)** Composition invariant — `model_id(Jacobian) = model_id(ValuationRecord)`:
$$j.\text{model\_id} = r.\text{model\_id} \quad \text{for } j, r \text{ used in same PnL-explain.}$$
`[type-level]`.

**(C2)** Composition invariant — `snapshot_input(Jacobian) = snapshot_input(ValuationRecord)` for a single pricing cycle.
`[runtime]`.

### L10 — `Move / Transaction / StateDelta / CDMBusinessEvent`

**(T1)** Type invariant — `Move.qty > 0` (positive decimal):
$$\forall m \in \text{Move}.\; m.\text{qty} \in \mathbb{D}_{>0}.$$
`[type-level]` via refined `Positive[Decimal]`.

**(T2)** Type invariant — `Move` parameterised by `Coordinate` (Single-Coordinate Move Principle): the type encodes which coordinate is touched.
`[type-level]`.

**(T3)** Type invariant — `Transaction.type` is a closed sum `{SETTLEMENT, COLLATERAL, LIFECYCLE, ACCOUNTING, CORRECTION}`; for `CORRECTION`, `corrects : TxnId` is required by the type.
`[type-level]` via refined records per case.

**(T4)** Type invariant — `Transaction.moves \in NonEmpty[Move] | Empty` and `Empty ⟹ state_deltas \ne []` (state-only transactions allowed; Ledger §17 Q1):
$$\text{moves}(t) = \text{Empty} \implies |\text{state\_deltas}(t)| \ge 1.$$
`[type-level]` via refined record.

**(W1)** Workflow invariant — conservation per `(txn_id, unit)`:
$$\forall t \in \text{Transaction}, \forall u \in \mathcal{U}.\; \sum_{m \in t.\text{moves}, m.\text{unit} = u} (\text{sign}(m) \cdot m.\text{qty}) = 0.$$
`[runtime]` at executor commit gate.

**(W2)** Workflow invariant — atomicity (P2): a transaction either commits all its moves and state-deltas or none.
`[runtime]` via WAL + executor.

**(W3)** Workflow invariant — referential integrity (P3):
$$\forall m.\; m.\text{src}, m.\text{dst} \in \text{dom}(\text{WalletRegistry}) \land m.\text{unit} \in \text{dom}(\text{UnitStore}).$$
`[runtime]` at executor.

**(W4)** Workflow invariant — append-only + hash chain (P4):
$$\forall n.\; \text{hash}(\Sigma[n]) \text{ includes } \text{hash}(\Sigma[n-1]).$$
`[runtime]` at append; `[type-level]` via hash-chained store interface.

**(W5)** Workflow invariant — single-writer per state-delta field (C11):
$$\delta.\text{writer\_handler} = \text{canonical\_writer}(\delta.\text{field}).$$
`[type-level]` via phantom-typed access tokens.

**(C1)** Composition invariant — `cdm_payload.cdm_version` recorded; `EventIntentEnum` is in that version's enum set.
`[runtime]` at validation.

**(C2)** Composition invariant — for `CORRECTION`: `corrects \ne None` and `corrects \in dom(\Sigma)`.
`[type-level]` + `[runtime]`.

### L11 — `Derived Projections` (`balance`, `V_t`, `avail`, settlement instruction, regulatory report)

**(T1)** Type invariant — every projection is declaratively a pure function of D1–D6:
$$\pi : \Sigma \times D_1 \times \ldots \times D_6 \to T \quad \text{(no internal state, no I/O).}$$
`[type-level]` via the projection function having no `IO` / `Ref` types.

**(W1)** Workflow invariant — regenerability:
$$\forall \pi, t.\; \pi(\text{cache}_t) = \pi(\text{recompute}(D_{1..6}, t)).$$
`[runtime]` via property-based test (recompute and assert equality).

**(C1)** Composition invariant — `balance(w, u, t) = w_0(u) + \sum_m \mathbb{1}[m.\text{unit}=u, m.\text{time} \le t] \cdot \text{sign}(m, w) \cdot m.\text{qty}$.
`[type-level]` (the formula IS the type; no other definition admitted).

**(C2)** Composition invariant — `V_t(w) = \sum_u \text{own}(w, u, t) \cdot P_t(u)$ where `P_t` requires `Quality(P_t) ∈ {FIRM, INDICATIVE}` for its inclusion.
`[runtime]` (quality gate).

**(C3)** Composition invariant — settlement instruction is total over `txn.type ∈ {SETTLEMENT, COLLATERAL}`.
`[type-level]` via case match.

### L12 — `Obligation / DischargePredicate / CompensationAction`

**(T1)** Type invariant — `Obligation` carries `(id, type, source, t_d, D, κ)` plus `state ∈ {Pending, Discharged, Compensated, Defaulted}` (closed sum with absorbing terminals):
$$o.\text{state} \in \text{TerminalSet} \implies \nexists\, e.\; \delta_o(o, e) \ne o.\text{state}.$$
`[type-level]`.

**(T2)** Type invariant — `D : LedgerState → Bool` is pure (no I/O), deterministic, total over reachable states.
`[type-level]` via the predicate's effect signature.

**(T3)** Type invariant — `κ : Obligation → PendingTransaction` is total (compensation always defined).
`[type-level]`.

**(W1)** Workflow invariant — P21 liveness:
$$\forall o, t > o.t_d.\; o.\text{state} \in \{\text{Discharged}, \text{Compensated}, \text{Defaulted}\}.$$
`[runtime]` enforced by Temporal durable timer at $t_d$.

**(W2)** Workflow invariant — P22 conservation under discharge: the discharge transaction satisfies $\sum_w \Delta = 0$.
`[runtime]` at executor commit.

**(W3)** Workflow invariant — P23 idempotency: the discharge predicate gates re-emission; replay is a no-op once discharged.
`[runtime]` via `(idempotency_token, source_event_id)` check.

**(W4)** Workflow invariant — handler totality (Lemma 5 of §14.7.5): every `(state, trigger)` pair reaches a terminal state in finite steps.
`[runtime]` (model-checked or property-tested).

**(C1)** Composition invariant — every state-changing event that creates an obligation registers it atomically with the event:
$$\text{handler}(e) \text{ returns } (\text{moves}, \text{state\_deltas}, \text{obligations}) \implies \text{Σ commit includes obligations.}$$
`[type-level]` (handler return type forces the obligation list, Ledger Principle 14.13).

### L13 — `WorkflowHistory / ActivityResult / FSMState`

**(T1)** Type invariant — `WorkflowHistory` is `NonEmpty[WorkflowEvent]`; `cdm_version`, `ledger_version` recorded.
`[type-level]`.

**(T2)** Type invariant — `ActivityResult` is keyed by `(wf_id, activity_id, input_hash)`; the memoisation map is content-addressed.
`[type-level]`.

**(T3)** Type invariant — `FSMState` is a closed sum on the FSM's state space (e.g., Valuation §2's eight states); transitions are typed functions taking a precondition proof object.
`[type-level]`.

**(W1)** Workflow invariant — workflow-code determinism: workflow code makes no random / clock / I/O call outside activities.
`[runtime]` via Temporal SDK enforcement.

**(W2)** Workflow invariant — replay determinism:
$$\forall h \in \text{WorkflowHistory}.\; \text{replay}(h) \text{ produces identical FSM trace.}$$
`[runtime]` (Temporal contract); `[type-level]` totality of `replay`.

**(W3)** Workflow invariant — for pure activities, `(input_hash, output)` is a function:
$$\text{ActivityResult}(\text{wf}, a, h_1) = \text{ActivityResult}(\text{wf}, a, h_2) \iff h_1 = h_2.$$
`[runtime]`.

**(C1)** Composition invariant — every `Move` in the event log traces back to a `(wf_id, activity_id, input_hash)`:
$$\forall m \in \Sigma.\; \exists\, (\text{wf}, a, h).\; m = \text{output}(\text{ActivityResult}(\text{wf}, a, h)).$$
`[runtime]` (audit-trail completeness).

### L14 — `WalletRegistry / Capability / KeyRegistry`

**(T1)** Type invariant — `WalletId` once registered has immutable `classification ∈ {Real, Virtual}`.
`[type-level]` via phantom-tagged classification.

**(T2)** Type invariant — `Capability` carries `(holder, granted_handlers, granted_scope, expiry)`; `Authorized[Capability]` refined subtype constructed only by signature verifier.
`[hybrid]`.

**(T3)** Type invariant — `KeyRegistry` is append-only; revocation is an event that never deletes a key, only marks it revoked-at-time.
`[type-level]`.

**(W1)** Workflow invariant — every move and every state-delta carries a verified actor reference:
$$\forall m \in \Sigma, \forall \delta \in m.\text{state\_deltas}.\; m.\text{actor} \in \text{ValidActor}_{m.\text{time}} \land \delta \text{ within actor's capability scope}.$$
`[runtime]` at executor authz gate.

**(W2)** Workflow invariant — capability scope respected (StatesHome C4 cross-overlay reads forbidden):
$$\forall \text{read}(s).\; s.\text{scope} \subseteq \text{capability}(\text{actor}, t).\text{granted\_scope}.$$
`[type-level]` via phantom-typed read tokens.

**(C1)** Composition invariant — every `OracleAttestation.signature` verifies under a key in `KeyRegistry` at attestation time:
$$\text{verify}(o.\text{signature}, o.\text{oracle\_id}, \text{KeyRegistry}_{o.\text{vendor\_timestamp}}) = \top.$$
`[runtime]`.

### L15 — `MarketDataSnapshot` (boundary of determinism)

**(T1)** Type invariant — content-addressed: `snapshot_id = SHA256(canonical(envelopes))`.
`[runtime]` at construction.

**(T2)** Type invariant — `coverage_manifest` enumerates every `(instrument_ref, observable_kind)` required for replay.
`[type-level]`.

**(W1)** Workflow invariant — `knowledge_timestamp(s) ≥ max(o.knowledge_timestamp for o in s.observations)`.
`[runtime]`.

**(W2)** Workflow invariant — append-only, point-in-time-as-of: replay-by-snapshot-id is reproducible bit-identically.
`[runtime]` (replay test).

**(C1)** Composition invariant — every `CertifiedCalibration`, `ValuationRecord`, `Jacobian`, `PnLAttribution` cites a `snapshot_id`; replays under that `snapshot_id` reproduce identical outputs.
`[runtime]` (canonical determinism property).

### L16 — `SmartContractCode / ModelCode (versioned)`

**(T1)** Type invariant — every contract version has `code_hash = SHA256(canonical(source))`; signed by deployment authority.
`[runtime]` at deployment.

**(T2)** Type invariant — `cdm_version_compat` is recorded; mid-trade-life version transitions restricted to backwards-compatible (Preserving) changes.
`[runtime]`.

**(W1)** Workflow invariant — every move records the contract version that produced it:
$$\forall m \in \Sigma.\; m.\text{source\_contract}.\text{code\_hash} \in \text{ContractRegistry}.$$
`[runtime]` at executor commit.

**(W2)** Workflow invariant — replay determinism: replays use the contract version active at original event time.
`[runtime]` via `source_contract.code_hash` resolution.

**(C1)** Composition invariant — `ValuationRecord.model_id` resolves to a `ModelCode.code_hash` in `ModelRegistry`; replays under that hash reproduce identical Greeks.
`[runtime]`.

---

## §3 — Totality of Accessor Functions

We enumerate every accessor / projection / decoder over the data layer and state its totality. Where partiality is unavoidable, we discharge via `Option` / `Result` / refinement.

| # | Accessor | Domain | Codomain | Totality story | Discharge |
|---|---|---|---|---|---|
| A1 | `lookup` | `UnitStore × UnitId` | `Option[UnitEntry]` | Total over `UnitId`; `Some` iff registered | `Option` |
| A2 | `terms` | `RegisteredUnitId` | `ProductTerms` | Total by construction (refinement) | refinement type `RegisteredUnitId` |
| A3 | `current_terms` | `RegisteredUnitId` | `TermsFields` | Total — head exists by `NonEmpty` | type-level (NonEmpty) |
| A4 | `terms_at` | `RegisteredUnitId × Time` | `TermsFields` | Total over `(u, t ≥ register_time(u))` | refined timestamp pair |
| A5 | `current_ref` | `(VendorId, ExternalRef)` | `Option[ReferenceData]` | Partial (vendor coverage) | `Option` |
| A6 | `is_business_day` | `(CalendarId, Date)` | `Option[Bool]` | Total over `effective_range` only | `Option` |
| A7 | `agreement_terms` | `(AgreementId, Date)` | `Option[AgreementVersion]` | Total once registered, partial pre-effective | `Option` |
| A8 | `lei_status_as_of` | `(LEI, Time)` | `Option[EntityStatus]` | Total once first known | `Option` |
| A9 | `unit_status` | `RegisteredUnitId` | `UnitStatus` | Total by C5 (registration-totality) | refinement type |
| A10 | `nav_at` | `RegisteredUnitId × Time` | `Option[IndexNAV]` | Partial before first publication | `Option` |
| A11 | `position_state` | `(WalletId, UnitId)` | `Option[PositionState]` | Genuinely 3-valued: `None`, `Some(zero)`, `Some(nonzero)` | `Option` (NOT a default-zero return) |
| A12 | `f(position_state(w,u))` for field f | `(W, U)` | `Option[T_f]` (lifted) | Total over the row when row exists | lift through Option |
| A13 | `position_vector` | `(EntityId, UnitId)` | `Option[PositionVector]` | Partial only when never held | `Option` |
| A14 | `avail / possess / encumb` | `PositionVector` | `Decimal` | **Total** by definition (pure projection) | none needed (computed) |
| A15 | `observations` | `(Ref, Kind, TimeRange)` | `List[RawObservation]` | Total — empty list when no data | `List` |
| A16 | `verify` | `OracleAttestation × KeyRegistry` | `Option[VerifiedAttestation]` | Partial (signature check may fail) | `Option` (sound by construction) |
| A17 | `snapshot` | `SnapshotId` | `Option[VendorSnapshot]` | Partial (not all ids exist) | `Option` |
| A18 | `current_calibration` | `(CalibrationId, Time)` | `Option[Certified[Calibration]]` | Partial pre-first-certification or after fallback | `Option` |
| A19 | `jacobian_at` | `(UnitId, ModelId, Time)` | `Option[Jacobian]` | Partial — depends on cycle | `Option` |
| A20 | `latest_firm` | `UnitId` | `Option[FirmRecord]` | Partial pre-first-FIRM-cycle | `Option` |
| A21 | `move_at` | `MoveId` | `Option[Move]` | Partial (id may not exist) | `Option` |
| A22 | `apply_all` | `List[Move]` | `LedgerState` | Total under valid prefix | precondition: prefix must satisfy P1-P3 |
| A23 | `txn` | `TxnId` | `Option[Transaction]` | Partial | `Option` |
| A24 | `replay` | `WorkflowHistory` | `WorkflowState` | Total under workflow-code determinism | precondition |
| A25 | `next_state` | `(FSMState, Event)` | `Option[FSMState]` | Total iff in transition relation; else explicit None (no implicit fall-through) | `Option` |
| A26 | `wallet_meta` | `WalletId` | `Option[WalletMetadata]` | Partial (un-registered) | `Option` |
| A27 | `current_capability` | `(Actor, Handler, Scope, Time)` | `Option[Capability]` | Partial (unauthorised) | `Option` |
| A28 | `balance` | `(Wallet, Unit, Time)` | `Decimal` | **Total** — projection of move stream prefix; default 0 | total |
| A29 | `V_t` | `(Wallet, Time)` | `Option[Decimal]` | Partial — depends on availability of FIRM `P_t(u)` for all `own(w,u) ≠ 0` | `Option` |
| A30 | `obligations_for` | `SourceRef` | `List[Obligation]` | Total — empty list valid | `List` |
| A31 | `discharge_predicate(o)` | `LedgerState` | `Bool` | **Total** by typing (pure, no I/O) | none |
| A32 | `compensation_action(o)` | `()` | `PendingTransaction` | **Total** by typing | none |
| A33 | `pattern_match` over CDM enums | `EventIntentEnum` | `T` | **Total** by closed-world; compiler-checked exhaustive | type-level |
| A34 | `settle_projection` | `Transaction` | `Option[SettlementInstruction]` | Total over `txn.type ∈ {SETTLEMENT, COLLATERAL}` | `Option` |
| A35 | `regulatory_report` | `(Transaction, Regime)` | `Option[Report]` | Partial — regime may not apply | `Option` |
| A36 | `as_of` | `(BitemporalRecord, KnowledgeTime)` | `Option[Record]` | Partial pre-first-knowledge | `Option` |

**Summary.** Of 36 accessors, 8 are **unconditionally total** (A14, A15-as-list, A28, A30, A31, A32, A33, plus the conservation projection); 5 are **total over a refined domain** (A2, A3, A4, A9, A22 with precondition); 23 are **partial, discharged via `Option`/`List`/`Result`**. No accessor returns a sentinel value or panics; partiality is typed.

**Critical totality discharge — Paulin-Mohring on `position_state`.** A11 is the singularly load-bearing case: the codomain MUST be `Option[PositionState]` and **`Some(zero) ≢ None`**. Defaulting `None` to `Some(zero)` would break wash-sale lookback, VM-settle replay, record-date entitlement reconstruction (StatesHome §2.2). The Phase 2 specification REQUIRES the storage layer to refuse a "delete row" API on `PositionState`.

---

## §4 — Termination Arguments

For every workflow that ingests, transforms, or persists data, we state the termination argument.

| # | Workflow | Class | Termination argument |
|---|---|---|---|
| T1 | Unit registration (D1) | bounded computation | structurally terminating (single pass over CDM Trade canonicalisation; bounded by trade size) |
| T2 | ProductTerms amendment | bounded computation | one append; predicate execution bounded by `\|TermsFields\|` |
| T3 | Reference data ingestion | bounded retry | `(a) bounded retry count` (default 5) + `(b) explicit timeout per request` (default 30s); decreasing measure: `retries_remaining` |
| T4 | Calendar ingestion | bounded computation | finite holiday set per calendar; sort + binary-search ingest |
| T5 | LEI / agreement ingestion | bounded retry | as T3 |
| T6 | Sanctions list ingestion | bounded retry + fail-closed | as T3 + fail-closed on persistent failure |
| T7 | Status update (D2 single field) | bounded computation | one StateDelta; no recursion |
| T8 | Position update (D3 single field) | bounded computation | as T7 |
| T9 | SBL move (single coordinate) | bounded computation | one move; one coordinate; two entities; no recursion |
| T10 | Raw observation ingestion | bounded retry | as T3 |
| T11 | Oracle attestation verification | bounded computation | one signature verification; bounded by signature length |
| T12 | Snapshot construction | bounded computation | one pass over the envelope set; bounded by snapshot size |
| T13 | Kalman calibration update (predict + update + project) | decreasing measure | (a) decreasing measure: $\|x_{t|t}^{(k+1)} - x_{t|t}^{(k)}\| \to 0$ in projection iteration, with hard iteration cap (default 50); (b) explicit timeout (default 5 min) |
| T14 | Jacobian computation (analytical / bump / AAD / pathwise) | bounded computation | bump = $O(n)$ in parameter count; AAD = $O(n)$; pathwise = $O(M \cdot n)$ for $M$ paths; explicit path / parameter cap |
| T15 | Pricing cycle (Valuation §6) | DAG traversal with topological order | DAG is finite, acyclic; topologically sorted; each node bounded; total termination by structural induction on DAG |
| T16 | PnL explain | bounded computation | linear in moves, units, and explained categories |
| T17 | Move append + hash chain | bounded computation | one hash, one append |
| T18 | Transaction commit | bounded computation | atomic write to WAL + apply state-deltas; bounded by `\|moves\| + \|state_deltas\|` |
| T19 | Settlement instruction projection | bounded computation | linear in moves of the transaction |
| T20 | Regulatory report projection | bounded computation | linear in transaction + reference-data lookups |
| T21 | Obligation registration | bounded computation | one append |
| T22 | Obligation discharge timer | bounded by deadline | (a) explicit deadline `t_d` + (b) compensation always defined; the timer fires at `t_d` and the discharge predicate is total → terminates in O(1) at `t_d` |
| T23 | Compensation action execution | bounded computation | as T18 |
| T24 | Workflow replay | structurally terminating | events list is finite (`NonEmpty[WorkflowEvent]`); replay is fold over events; terminates by structural induction |
| T25 | Activity invocation (with retry) | bounded retry | retry policy with maximum attempts and timeout; the **decreasing measure is `attempts_remaining`** (Avigad: "every retry must reduce a counter; otherwise termination is wishful thinking") |
| T26 | FSM transition | bounded computation | one transition; absorbing terminals reachable in bounded steps (Lemma 5 of §14.7.5) |
| T27 | Capability check | bounded computation | linear in scope set |
| T28 | Replay from snapshot | structurally terminating | snapshot is finite; replay fold is structural |
| T29 | Reconciliation against custodian statement | bounded computation | linear in statement holdings |
| T30 | Smart-contract handler invocation | bounded computation | smart contracts are pure deterministic functions; inputs bounded; loops must be bounded by input size (no unbounded recursion permitted) |

**Coquand on T30**: "A smart contract that does not statically bound its loops is a smart contract that does not terminate. Bounded recursion is the only honest discipline."

**Loops over external sources (the brief's question).** Every external-source loop MUST satisfy at least one of:
- (a) **bounded retry** (T3, T5, T10, T25): explicit `max_retries`, decreasing measure `retries_remaining`;
- (b) **explicit timeout** (T3, T13, T25): wall-clock bound;
- (c) **decreasing measure** (T13, T22): explicit progress metric (Kalman projection convergence; deadline timer).

Workflows that fail all three are rejected at design review (this is the FORMALIS Phase 2 acceptance criterion for new workflows).

---

## §5 — Determinism Postconditions

For every activity that crosses the determinism boundary (i.e., consumes external data and produces ledger-internal state), we state the postcondition that downstream replay can rely on.

**Stance (de Moura):** "Determinism is not a coincidence; it is a contract. State the contract; enforce the contract; verify the contract."

**Boundary 1 — Reference data ingestion** (`ingest_reference_data`).
**Postcondition:** `∃! r ∈ ReferenceMaster.` `r.payload_hash = SHA256(canonical(input))` `∧` `r.knowledge_timestamp = t_now` `∧` `r.vendor_timestamp = parsed(input.timestamp)`. Replay: given the same input bytes and `t_now`, the same `r` is produced.

**Boundary 2 — LEI status as of `t`** (`lei_status_as_of`).
**Postcondition:** the function returns the bitemporally indexed status; replay yields identical results across system restarts because `(authority_publication_time, knowledge_time)` are immutable record fields.

**Boundary 3 — Raw observation ingestion** (`ingest_observation`).
**Postcondition:** `o.bitemporal_pair` immutable; `o.signed_attestation` retained; the observation is content-addressed by `(vendor, ref, kind, vendor_timestamp)`; restatement appends a new row, retaining the original.

**Boundary 4 — Snapshot construction** (`make_snapshot`).
**Postcondition:** `snapshot_id = SHA256(canonical(envelopes))` and `replay(snapshot_id)` returns the same envelope set; the snapshot is the **canonical determinism boundary** for downstream pricing.

**Boundary 5 — Kalman calibration** (`calibrate(snapshot_id, model)`).
**Postcondition:** given the same `snapshot_id`, the same `model_id`, and the same prior $x_{t-1|t-1}$, $P_{t-1|t-1}$, the certified posterior $x_{t|t}^{\text{certified}}, P_{t|t}^{\text{certified}}$ is bit-identical. Achieved by: (i) `Decimal` arithmetic everywhere (no IEEE-754 in deterministic paths); (ii) deterministic linear-algebra routines (no nondeterministic-order BLAS reductions); (iii) deterministic projection onto $\Theta_{AF}$.

**Boundary 6 — Pricing** (`price(unit, snapshot_id, model_id, calibration_id)`).
**Postcondition:** `ValuationRecord` is content-addressed by `(unit_id, timestamp, model_id, snapshot_input, calibration_id)`; replay produces identical `dirty_price`, `clean_price`, `accrued`, Greeks. The Greeks computation method is recorded for audit; AAD vs bump must produce identical results within explicit tolerance.

**Boundary 7 — PnL explain** (`explain(record_t, record_{t-1}, jacobian)`).
**Postcondition:** decomposition is deterministic given the same `(record_t, record_{t-1}, jacobian)`; residual is bit-identical.

**Boundary 8 — Move emission** (smart-contract handler invocation).
**Postcondition:** given the same `(handler_input, contract_code_hash, executor_state_at_event_time)`, the handler produces identical `(moves, state_deltas, obligations)`. Achieved by: (i) `Decimal` arithmetic; (ii) handler is a pure deterministic function (Ledger §5, §7.6); (iii) no clock / random / I/O in handler body.

**Boundary 9 — Activity result memoisation** (Temporal activity).
**Postcondition:** for pure activities, `(activity_id, input_hash) ↦ output` is a function; replay returns the memoised output. Non-pure activities (oracle calls, RPC) are wrapped in `IngestionGate` that signs the result and stores it as a `RawObservation` — the Temporal activity then becomes pure over `(observation_id)`.

**Boundary 10 — Workflow history replay** (Temporal `replay`).
**Postcondition:** `replay(history)` produces identical FSM trace (Ledger §14.10 alignment). Achieved by: workflow-code determinism (W1 of L13).

**Boundary 11 — Settlement instruction projection** (`project_to_settlement`).
**Postcondition:** the projection is a pure deterministic function of the transaction, reference data, and SSI; given the same triple, the same instruction is produced (including `EndToEndId`, which is content-addressed).

**Boundary 12 — Regulatory report projection** (`project_to_drr`).
**Postcondition:** deterministic given `(transaction, regime, mapping_version, cdm_version)`; mapping versions recorded so replay under the same versions produces bit-identical reports.

**Boundary 13 — Hash chain append** (`append_to_log`).
**Postcondition:** `Σ[n+1].prev_hash = SHA256(Σ[n])`; deterministic given the predecessor and the canonical encoding of the new entry.

**Cross-cutting determinism predicate (DET).** The Ledger v11.0 system satisfies **(DET)** if for every $(t, \text{snapshot\_id}, \text{contract\_versions}, \text{model\_versions}, \text{cdm\_version})$:
$$\text{Replay}(t, \text{snapshot\_id}, \text{versions}) = \text{Original}(t).$$
Boundaries 1–13 collectively imply (DET) modulo the assumption that no non-deterministic primitive is introduced in handler code (the Coquand-rule on workflow code).

---

## §6 — Compositional Correctness Theorems

We state five cross-cutting theorems of the form "if data layer satisfies $X$ and executor satisfies $Y$, then ledger satisfies $Z$." These will become the invariants section of the LaTeX document.

**Theorem 1 (Conservation Lifting).**
*Hypotheses.*
- (D-CONS) The data layer satisfies: for every event class, the handler-emitted moves satisfy $\sum_w \Delta w(u) = 0$ (StatesHome C2; Ledger §2.4 Theorem).
- (E-ATOM) The executor satisfies: every transaction is committed atomically (P2) or rolled back; no partial commits.
- (D-IDX) Every move references a `RegisteredUnitId` and `RegisteredWallet` (referential integrity P3).

*Conclusion.* The ledger satisfies global conservation:
$$\forall t \ge 0, \forall u \in \mathcal{U}.\; \sum_{w \in \mathcal{W}} \text{balance}(w, u, t) = \sum_{w \in \mathcal{W}} \text{balance}(w, u, 0) + \sum_{e \in \Sigma_{[0,t]}, e.\text{type} = \text{ISSUANCE}} \Delta_e^{\text{ext}}.$$

*Proof sketch (Avigad).* Induction on $|\Sigma_{[0,t]}|$. Base: $t = 0$, vacuous (StatesHome C9). Step: a new transaction either preserves the sum (D-CONS handler-level) or is rejected (E-ATOM); either way the invariant is preserved. The key data-layer hypothesis is D-CONS — without it, the executor cannot validate; without E-ATOM, individual moves may commit out of conservation pairs.

**Theorem 2 (Replay Determinism Lifting).**
*Hypotheses.*
- (D-DET) Every external attestation is content-addressed and signed; `Decimal` arithmetic everywhere; raw observations and snapshots are append-only (boundaries 1–4 of §5).
- (D-CODE) Every smart-contract version and pricing-model version is content-addressed; the version active at event time is recorded with the event.
- (E-WF) The workflow runtime (Temporal) replays workflow code deterministically given identical history; activities are memoised on `input_hash`.

*Conclusion.* The ledger satisfies replay determinism:
$$\forall t.\; \text{Replay}(t, \text{Σ}_{[0,t]}, \text{versions}) = \text{Original}(t)$$
bit-identically.

*Proof sketch (Leroy, after CompCert).* Decomposition pass-by-pass: ingestion (Boundary 1, 3) is deterministic by content-addressing; calibration (Boundary 5) by D-DET (Decimal + deterministic linear algebra); pricing (Boundary 6) by D-CODE + Boundary 5; handlers (Boundary 8) by D-CODE + Decimal; orchestration (Boundary 10) by E-WF; settlement / reporting (Boundary 11, 12) by mapping-version pinning. Composition: each pass is a pure function of its inputs; equality of inputs + equality of code ⟹ equality of outputs.

**Theorem 3 (Obligation Liveness Lifting).**
*Hypotheses.*
- (D-OB) Every state-changing event whose handler creates an obligation registers it in the obligation registry atomically with the event (Ledger Principle 14.13; L12.C1).
- (D-DD) The discharge predicate $D$ is total over reachable ledger states; the compensation action $\kappa$ is total.
- (E-TIMER) The Temporal runtime fires durable timers at deadlines $t_d$ and the discharge handler runs to terminal state in finite steps (Lemma 5 of §14.7.5).

*Conclusion.* The ledger satisfies P21 (liveness):
$$\forall o \in \text{Obligations}, \forall t > o.t_d.\; o.\text{state} \in \{\text{Discharged, Compensated, Defaulted}\}$$
and P22 (conservation under discharge), P23 (idempotency).

*Proof sketch (de Moura).* By D-OB, every obligation is registered. By E-TIMER, the deadline timer fires. By D-DD, both $D$ and $\kappa$ are total — $D$ either succeeds (Discharged) or fails ($\kappa$ executes producing a transaction satisfying conservation P22 by Theorem 1). The handler reaches a terminal state in finite steps by Lemma 5. P23 follows from `(idempotency_token, source_event_id)` deduplication.

**Theorem 4 (Substantiation: Balance Sheet IS the Ledger).**
*Hypotheses.*
- (D-PROJ) Every D7 derived projection (`balance`, `V_t`, `avail`, settlement instruction, regulatory report) is a pure deterministic function of D1–D6 (L11.W1).
- (D-SEM) D6 (`Move`, `Transaction`, `StateDelta`, `CDMBusinessEvent`) is the unique source of state mutation (no mutation outside committed events).
- (E-COMMIT) The executor's commit gate enforces conservation, atomicity, referential integrity, append-only hash chaining (P1–P4) at every commit.

*Conclusion.* For every reportable quantity $Q \in \{\text{balance sheet, P\&L, regulatory report, settlement state, NAV}\}$:
$$Q(t) = \pi_Q(D_{1..6}(t))$$
where $\pi_Q$ is the corresponding projection. In particular, the balance sheet at $t$ is identically the ledger replayed to $t$ — the multi-source-of-truth bug (Ledger §1) is impossible by construction.

*Proof sketch (Coquand).* By D-PROJ, $\pi_Q$ has no internal state. By D-SEM, the only inputs to $\pi_Q$ are D1–D6. By E-COMMIT, D6 is consistent (P1–P4). Therefore the projection is well-defined and equal across all observation points; in particular, the cached value (D7) is regenerable from D1–D6 (L11 invariant).

**Theorem 5 (No-Arbitrage Pricing Lifting).**
*Hypotheses.*
- (D-CAL) `CertifiedCalibration.state_vector ∈ Θ_AF` (no-arbitrage admissible region; L9.T1).
- (D-MOD) `Jacobian.model_id = ValuationRecord.model_id` (model-consistency, Valuation Remark 3.13; L9.C1); both cite the same `snapshot_input` (L9.C2).
- (D-FIRM) `Quality(P_t(u)) = FIRM ⟹ fsm_state(u) = Explained` (PnL-explain pass; L9.W2).
- (E-GATE) The pricing executor's certification gate enforces (D-CAL); the FSM enforces (D-FIRM).

*Conclusion.* Every official PnL, every regulatory mark, every NAV strike that consumes a `FirmRecord` is no-arbitrage-consistent:
$$\forall u, t.\; r \in \text{FirmRecord}(u, t) \implies r.\text{dirty\_price} = E^{\mathbb{Q}}[\text{payoff}(u) | \mathcal{F}_t]$$
in the certified-calibration measure $\mathbb{Q}$.

*Proof sketch (Paulin-Mohring).* `FirmRecord` is constructible only via the certifier's smart constructor, which requires (D-CAL) and (D-MOD) as input. (D-FIRM) ensures the PnL-explain residual is within tolerance — the model is observationally consistent with the calibrated parameters. (E-GATE) prevents an uncertified or non-explained record from being labelled FIRM. The conclusion is by composition of refinement types: $\text{Certified}[\text{Calibration}] \times \text{ModelConsistent}[\text{Jacobian, Record}] \times \text{Explained}[\text{Record}] \to \text{FirmRecord}$.

---

## §7 — Cross-Reference Map (D-tier ↔ Phase 1 enumerations)

For Phase 3 arbitration. All 19 Phase 1 enumerations converge to the L1–L16 leaves modulo regrouping:

| Leaf | NAZAROV | correctness | grothendieck | jane_street | halmos | minsky | feynman | cartan | finops | isda | sbl | temporal | matthias | noether | karpathy | lattner | geohot | testcommittee | formalis Phase 1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| L1 UnitIdentity | A.1.x | C1, C8a | $\mathcal{F}_{\text{Defn}}$ | §1 ProductTerms | D3 | F9.1 | §1, §2.1 | §2.2 | F5 | §1.1, §1.2 | §1.x | §3.1 | §1a, §1b, §8a | §1.1 | static-1 | §2-3 | covered | covered | D1.1, D1.2 |
| L2 ReferenceMaster | B (tables) | C2 | $\mathcal{F}_{\text{Defn}}$ | §2 | D1, D2 | F2, F3 | §2 | §1.4, §1.5, §2.4-2.6 | F2 | §2.3 | §2.1-§2.8 | §1.3, §1.4 | §2 | §2.1, §2.2 | refs | §5 | covered | covered | D1.3-D1.5, D1.7 |
| L3 LegalAgreement | A.1.6 | C2.x | $\mathcal{F}_{\text{Defn}}$ | §2.3 | D2 | F4 | §1.6 | §2.7 | F4 | §1.3, §7.1, §7.2 | §1.4-§1.7 | §2.3 | §2 | §1.3 | refs | §4 | covered | covered | D1.6 |
| L4 Party / LEI | A.1.1, B (auth tables) | C2.1 | $\mathcal{F}_{\text{Defn}}$ | §2.3 | D2 | F3 | §2.3 | §2.3 | F3 | §2.1 | §1.1 | §2.2 | §11 | §1.3, §9 | refs | §3 | covered | covered | D10.1 partial |
| L5 UnitStatus | E (config) | C8b | $\mathcal{F}_{\text{Eff}}$ | §5.4 | D4 | F9.2 | §5.5 | §9.2, §10.1 | F9 | §5.2 | §5.3 | §2.1, §4b | §8b | §5.1 | state | §9.2 | covered | covered | D2.1, D2.2 |
| L6 PositionState | E | C8c | $\mathcal{F}_{\text{Eff}}$ | §5.3 | D5 | F9.3 | §5.4 | §9.3 | F9 | §5.3 | §5.x | §5.3 | §8c | §5.2 | state | §9.3 | covered | covered | D3.1, D3.3 |
| L7 PositionVector | E | C8c (extended) | $\mathcal{F}_{\text{Eff}}$ | §5.3 | D5 | F9.3 | §5.4 | §9.4 | F9 | §5.3 | §5.x | §5.3 | §15 | §5.3 | state | §9.4 | covered | covered | D3.2 |
| L8 RawObs / Oracle / Snap | C, D | C3, C4 | $\mathcal{F}_{\text{Obs}}$ | §3a, §4 | D8, D10 | F6, F7.2 | §3.1, §3.5, §4.1 | §4 | F6 | §3.1, §4.1-§4.3 | §3.x, §4.x | §4a, §4b.2 | §3 | §3, §4 | obs | §6, §7 | covered | covered | D4.1-D4.3 |
| L9 Calib / Jac / Valuation | C, E.5.2-5.3 | C8 (Cal.), C9 (Val.) | $\mathcal{F}_{\text{Obs}}$, $\mathcal{F}_{\text{Eff}}$ | §3b | D9 | F7, F12 | §3.2-3.4 | §5.2-§5.3 | F7, F12 | §3.2, §3.3, §9.1 | covered | §4b | §9 | §3.2 | calib | §6, §8.4 | covered | covered | D5.1-D5.3 |
| L10 Move / Txn / StateDelta / CDM | E (outputs F) | C5, C7 | $\mathcal{F}_{\text{Eff}}$ | §5.1, §5.2 | D7, D11 | F8 | §5.1-§5.3, §5.6 | §8 | F8 | §5.1, §5.4, §5.5 | §5.1, §5.2 | §5.1-§5.4 | §7 | §5.4, §5.5 | exec | §8 | covered | covered | D6.1-D6.4 |
| L11 Derived Projections | F | C9, C10, C14 | (cache; not a sheaf) | §5 (impl) | D14 | F11, F12 | §3.3, §5.x | §8.3 | F11 | §10.x | covered | §4b.3, §4b.5 | §10, §14 | §5.3 | proj | §8 | covered | covered | D7.1-D7.5 |
| L12 Obligation | E (config / governance) | C18 | $\mathcal{F}_{\text{Eff}}$ extended | §5.6 (idem.) | D13 | F10 | §5.8 | §10.1 | F10 | §8.1, §8.2 | §5.5 | §7.x | §18 | §5.6 | obligation | covered | covered | covered | D8.1-D8.3 |
| L13 Workflow / Activity / FSM | E | C9b (Cal.), C9d (DAG) | (orchestration) | §5.5 | D11 | covered | §5.7 | §9.5, §9.6 | covered | §5.5 | covered | §8.x | covered | covered | covered | covered | covered | covered | D9.1-D9.3 |
| L14 Wallet / Capability / Key | A (identity), CC-9 | C11 | $\mathcal{F}_{\text{Defn}}$ | §7.3 | D6 | F1 | §7.x | §3.x | F1 | covered | §1.2 | covered | covered | covered | covered | §3.4 | covered | covered | D10.1-D10.3 |
| L15 Snapshot (boundary) | CC-2 | C3.x | $\mathcal{F}_{\text{Obs}}$ | §3a (raw) | D8 | F7.2 | §3.5 | §6.3 | F7.2 | §3.1 | §3.6 | §4b.2 | §3 | §3 | snap | §6.3 | covered | covered | D4.3 (split) |
| L16 SmartContract / Model code | E.5.1-5.2 | C1.2 | $\mathcal{F}_{\text{Defn}}$ | §3b (model) | D11 | F12 | §1.2 | §2.5 | F12 | covered | covered | §1.2 | covered | covered | covered | covered | covered | covered | D9 partial + new |

(Empty cells indicate the enumeration did not name this leaf as a primary category; "covered" indicates implicit treatment.)

The convergence is **strong**: 16/16 leaves are addressed by every enumeration up to relabelling. Phase 3's sole remaining decisions are (a) tier numbering vocabulary; (b) whether to merge L8+L15, L8+L9, L13+L10, L4+L14; (c) whether L16 is its own tier or under L1.

---

## §8 — Underspecified Items (Phase 2 hand-off list)

Carried forward from FORMALIS Phase 1 §14, with refinement after Phase 1 cross-reading. These should be flagged for Phase 3 / LaTeX:

1. **Tax-lot data** (L6 sub-tier; matthias §16, sbl absent, finops F4, lattner absent). Recommend `(WalletId, UnitId, LotId)` keyed sub-tier with explicit identification methods.
2. **XVA / impairment / ECL** (matthias §10 partial). Recommend tier `D5.4 AdjustmentBucket` keyed by `(LegalEntity, Counterparty, AdjustmentKind)` with virtual-wallet conservation.
3. **PII / GDPR shadow store** (matthias §11 partial; Ledger §15 OP9). Recommend tier D11 separate from immutable D6 with crypto-shred key registry.
4. **Multi-entity consolidation** (finops F1 partial; Ledger §15 OP). Recommend D7 derived projection with versioned elimination rules.
5. **Repo / GMRA-specific terms** (sbl partial under §1.6 triparty agreement; Ledger §15 OP). Cleanly fits L1 with `kind = REPO`.
6. **Pre-trade limit data** (Ledger §15 OP). Recommend L1 sub-tier "LimitContract" — versioned, append-only, signed by Risk.
7. **Locate state** (sbl §5.6; Ledger §15.16). Adopt time-limited-Unit approach + L12 obligation entry for locate-expiry.
8. **Reference-data lineage and vendor-version coexistence** (L2). Per-vendor registries with explicit consensus or primary-source rule, bitemporal on each.
9. **Tokenised-asset backing attestation** (NAZAROV §1.7; Ledger §10.6). Cross-tier — L1 (reference) + L8 (oracle attestation) + L14 (key registry); requires explicit "custodian-is-flat" composition theorem.

---

## §9 — Verification Stance (FORMALIS Phase 2 acceptance criteria)

Per the FORMALIS test (system prompt), Phase 2 is acceptable iff:

1. **Specification.** Every leaf has a stated invariant (§2). 16/16 covered.
2. **Types.** Every leaf has either a closed sum, a refined record, a phantom-typed indexing, or a runtime-checked refinement (the `[type-level]` / `[runtime]` / `[hybrid]` annotations). No leaf relies on convention.
3. **Invariants.** Every leaf has type, workflow, and composition invariants stated in formal notation (§2). Cross-cutting invariants (Phase 1 §13's I1–I20) are *summed up* in §6 Theorems 1–5.
4. **Totality.** Every accessor's totality is stated either as unconditional, conditional on registration, or explicitly partial via `Option` (§3, 36 accessors).
5. **Determinism.** 13 boundary postconditions (§5) covering arithmetic, snapshots, calibration, pricing, handlers, workflow replay, settlement, regulatory reporting, and hash chaining.
6. **Composition.** 5 cross-cutting theorems (§6) — Conservation Lifting, Replay Determinism Lifting, Obligation Liveness Lifting, Substantiation, No-Arbitrage Pricing Lifting.

— end of FORMALIS Phase 2 contribution —

> "Without a termination argument, every workflow is a hope. With one, every workflow is a theorem."
> — Christine Paulin-Mohring, closing the Phase 2 deliberation.
