# Phase 1 - Independent Data Enumeration (geohot)

**Posture.** Radical simplicity. Delete aggressively. Beauty as diagnostic. Anti-cargo-cult. Every line of schema is a liability. The code (and the data dictionary) you delete is the data that can never be wrong.

**Source contract.** Ledger v10.3 + StatesHome addendum (3-map ruling: ProductTerms, UnitStatus, PositionState; no W-sector economic state) + valuation v1.0 (FSM + ValuationRecord + Pricing DAG + Kalman). The framework's real primitives are **unit, wallet, move, transaction, smart contract, lifecycle event, price, attestation**. Anything that is not one of these or a strict projection of these is suspect.

**Method.** For each candidate category I ask three questions, in this order:
1. Is it derivable from another category? (If yes - delete; it is a view, not a category.)
2. Is its mutation discipline distinct? (If no - merge with the category that shares its discipline.)
3. Could the framework function for one quarter without it? (If yes - it is policy or analytics, not data.)

Items that survive get the seven mandatory fields plus the three geohot fields (delete-test, LoC budget, over-engineering pattern).

---

## Floor disagreements (stated up front)

The proposed six floor categories collapse to **four** under this discipline. The reorganisation is:

| Floor (proposed) | Geohot ruling |
| --- | --- |
| 1. Static | **MERGE** with Reference. The "static" / "reference" split is a vendor-feed artefact, not a semantic distinction. ProductTerms (immutable, versioned-append-only) covers both. |
| 2. Reference | Becomes **D1 - ProductTerms** (with Wallet/Party registry split into D2 and Index/Calendar identity into D5). |
| 3. Market | **SPLIT**. Raw vendor quotes (D3-Attestations) and certified parameter state (D4-CalibrationState) are different data with different mutation discipline; collapsing them under "market data" is the over-engineering trap that justifies a giant tier-1 EOD warehouse. |
| 4. Oracle | **SUBSUMED** by D3-Attestations. "Oracle" is a CDM word for "price feed with attribution"; it is not a separate category, it is the provenance contract on Attestations. Deleting the word saves a chapter. |
| 5. Smart-contract execution | **MERGE** with the move stream. Smart-contract output IS moves + StateDelta. The only thing left after that merge is "what state did the contract read?" - which is provenance metadata on the move, not its own category. |
| 6. Listed-instrument detail | **NOT A CATEGORY**. Listed vs. OTC is a fungibility predicate on ProductTerms, not a separate data sector. NKY-future-on-JPX and AAPL-call-CBOE-OCC live in the same ProductTerms map, distinguished by a `venue` field. Promoting "listed-instrument detail" to top-level is exchange-cargo: it duplicates what unit identity already disambiguates. |

**The real categories.** What remains after these collapses:

| # | Name | Mutation discipline | Conservation? |
| --- | --- | --- | --- |
| D1 | ProductTerms | Versioned append-only (per StatesHome C6/C7) | n/a (definitional) |
| D2 | WalletRegistry | Mutable, non-economic sidecar (per StatesHome) | n/a (no balances) |
| D3 | Attestations | Append-only event stream (timestamped, signed) | per-source provenance, not value |
| D4 | CalibrationState | Mutable map, Kalman-posterior carrier | covariance-bounded, not zero-sum |
| D5 | UnitStatus | Mutable map, shared per unit (per StatesHome) | not conserved (lifecycle-only) |
| D6 | PositionState | Monotone carrier, Option accessor (per StatesHome C1) | per-event-class structural (C2) |
| D7 | MoveStream | Hash-chained append-only log | conservation by construction |
| D8 | ValuationRecord | Append-only per (unit, t, model) | n/a (derived) |
| D9 | ObligationStore | Monotone carrier with closed-state terminal | n/a (liveness, not value) |

Nine categories, not six. Three of them (D7, D8, D9) are not in the proposed floor at all - and one of them (D7-MoveStream) is the most important data category in the entire framework. Omitting the immutable event log from a "data enumeration" of the Ledger is the framework equivalent of writing a kernel spec without listing the page table. The proposed floor leaks the framework's own definition.

---

## D1. ProductTerms

1. **Canonical name.** `ProductTerms[u]` -> `NonEmpty[TermsVersion]`.
2. **Definition.** The immutable, versioned-append-only specification of what a unit *is*. Holds every field that a holder is economically indifferent to mutating without re-identifying the instrument. CME-ES and ICE-ES are distinct entries; AAPL pre-split and post-split are distinct entries (per C8 fungibility-breaking amendment).
3. **Minimum field set.** `unit_id` (deterministic from CDM object); `unit_type` enum (CASH | EQUITY | LISTED_DERIV | OTC_DERIV | BOND | STRUCTURED); `currency` (ISO 4217); `terms_blob` (CDM Trade or contract-spec object - a single opaque field, not 80 split fields); `smart_contract_ref`; `is_fungibility_preserving` predicate. **That is six fields, not the fifteen-field UnitEntry of v10.3 sec 3.3.3.** Multiplier, expiry, ISIN, contract_spec, cdm_trade_ref are all inside `terms_blob` because they are CDM-shaped already.
4. **Identity.** `unit_id = hash(canonical_serialise(terms_blob))`. Injective by construction. No counter, no UUID, no surrogate key.
5. **Provenance.** `created_by: TransactionId`, `created_at: Timestamp`. That is it. The CDM source document is the `terms_blob` itself.
6. **Temporal semantics.** Append-only `NonEmpty[TermsVersion]`. Each version stamped with effective range. `current()` is the head; `as_of(t)` is a fold. C6 + C7 (StatesHome) are non-negotiable.
7. **Failure consequences.** Loss of ProductTerms[u] = unit becomes unparseable; every Move referencing u becomes invalid; conservation still holds (quantities are intact) but pricing and lifecycle are dead. **Restorable from CDM source** if the CDM payload is preserved in D7 (move stream); otherwise unrecoverable. This is why D7 is the canonical record and D1 is the index, not the reverse.

**(a) Delete test.** Delete `lifecycle_stage` from D1 - it lives in D5/UnitStatus. Delete `created_by` and `created_at` - reconstructible from D7's first registration move. The minimum is `(unit_id, terms_blob, smart_contract_ref, fungibility_predicate)`. Four fields. Framework still works: registration fails, lookup works, amendment works.

**(b) LoC budget.** Ingest from CDM Trade object: **12 lines**. `serialise -> hash -> insert if-not-present -> append-version-if-fungible-else-allocate-new-uid`. The reference impl in StatesHome addendum sec 9 does it in 8 lines.

**(c) Worst over-engineering pattern.** A "Tier 1 / Tier 2 / Tier 3" registry with separate database tables for "reference data," "product registry," and "unit registry" - exactly what v10.3 sec 3.3 currently proposes. This is three indices over the same data, with synchronisation cost that scales with squared corner-case count. Fight it. One map, one key, one write path.

---

## D2. WalletRegistry

1. **Canonical name.** `WalletRegistry[w]` -> `WalletMetadata`.
2. **Definition.** Non-economic sidecar of every wallet that has ever existed. KYC tags, legal entity reference (LEI), permission/capability scopes, audit cursor. **Not state.** No balances. No PnL. Per StatesHome ruling: there is no W-sector economic state.
3. **Minimum field set.** `wallet_id`, `kind` enum (REAL | VIRTUAL_COUNTERPARTY | INTERNAL_BOOK), `lei: Option[LEI]`, `caps: Set[Capability]`. Four fields. KYC documents are an external system (compliance), not a Ledger column - they get a foreign key, not embedding.
4. **Identity.** `wallet_id`: deterministic name. For virtual counterparties, `wallet_id = lei + ":" + account_suffix` per v10.3 sec 2.5.
5. **Provenance.** Created by an admin transaction; that transaction lives in D7 and is the audit trail. No separate provenance fields.
6. **Temporal semantics.** Mutable but rarely. KYC re-verification updates a row in place. **No versioning.** If you need wallet-history queries, replay D7 - that is what time travel is for.
7. **Failure consequences.** Loss of WalletRegistry = settlement instructions cannot be enriched with LEI/SSI; capability checks fail-closed; **no economic data lost** (balances are computed from D7). Operational outage, not corruption.

**(a) Delete test.** Delete `kind` - derivable from whether the wallet appears as source/destination in real-vs-virtual contexts in D7. Risky. Keep it as a denormalised cache with an invariant. Delete `audit_cursor` if present - it is per-consumer state, not Registry state. Minimum: `(wallet_id, lei, caps)`. Three fields.

**(b) LoC budget.** Trivial map-with-permission-check. **20 lines** including capability evaluation.

**(c) Worst over-engineering pattern.** Treating WalletRegistry as a "user model" with addresses, contact info, hierarchical org structure, multi-tenant carve-outs. None of that is the Ledger's business. The framework is an accounting engine, not a CRM. If a field is not consulted by the executor or the settlement projection, it does not belong here.

---

## D3. Attestations (raw market observables + oracle outputs)

1. **Canonical name.** `Attestations` -> append-only stream of `Attestation` records.
2. **Definition.** Every external assertion that enters the system: exchange tick, vendor curve point, dealer quote, settlement-price publication, dividend announcement, settlement confirmation. **Single category for all of them.** "Oracle" is the contract this category satisfies (signed, timestamped, source-attributed) - it is not a separate category.
3. **Minimum field set.** `attest_id` (hash), `topic: AttestKey` (e.g. `("AAPL.US", LAST)` or `("ES.CME", SETTLE_2026-04-29)`), `value: Decimal | Json`, `t_obs: Timestamp` (when the world produced it), `t_known: Timestamp` (when the system learned it), `source: SourceId`, `signature: Bytes`. Seven fields. **`t_obs` and `t_known` both load-bearing** - bitemporal is non-negotiable for time travel, vendor restates, and the Calibration Manifesto's "as known at time t" replay.
4. **Identity.** `attest_id = hash(topic, value, t_obs, source)`. Idempotent ingest by construction.
5. **Provenance.** `source` + `signature` IS the provenance. No separate provenance table.
6. **Temporal semantics.** Append-only. Late-arriving attestations and vendor restates are *new rows* with later `t_known` and same or different `t_obs` - never overwrites. The valuation FSM's "snapshot at t" is `latest-by-t_known where t_known <= t`.
7. **Failure consequences.** Loss of Attestations = no pricing; FSM fills with STALE/FAILED; D7 (move stream) is unaffected because trade-date positions are preserved; system continues to settle past trades from D4 and D8 caches. Replayable from vendor archives (most vendors do support that).

**(a) Delete test.** Delete the separate "Oracle" category that v10.3 sec 9.3 hints at - it is just Attestations with a CDM-synonym envelope. Delete any "primary vs derived market data" split (per v10.3 sec 21.4 conclusion: "the traditional distinction between primary and derived market data adds no value"). One stream. One ingest path. If the framework runs without one of those distinctions for a quarter, it never needed it.

**(b) LoC budget.** Append-only log + bitemporal index + signature verify. **60 lines** for the ingest path; the index is a btree keyed on `(topic, t_known)`.

**(c) Worst over-engineering pattern.** A "Market Data Service" with a typed schema per vendor (Bloomberg fields, Refinitiv fields, exchange fields...) and per-asset-class normaliser. This is the cost driver in every real risk system. Wrong direction. **Store the raw payload as bytes, index on `(topic, t_known)`, normalise lazily at consumption.** Normalisers are pure functions in D4 (calibration), not D3 columns. Never let vendor-specific fields creep into the storage schema.

---

## D4. CalibrationState

1. **Canonical name.** `CalibrationState[c]` -> `(x, P, t_last_update)` where `c` is a calibrated object (yield curve, vol surface, hazard curve), `x` is the posterior mean (parameter ket), `P` is the covariance.
2. **Definition.** The Kalman posterior at the most recent observation epoch for each calibrated object, plus enough history to support innovation gating and replay. This is the **certified parameter state** consumed by the Pricing DAG leaf nodes (valuation v1.0 sec 6).
3. **Minimum field set.** `cal_id: CalibrationKey`, `x: Vector[Decimal]`, `P: Matrix[Decimal]`, `t_last: Timestamp`, `source_attestations: Set[AttestId]` (which D3 rows fed this update), `certified: Bool` (passed no-arb projection, gating, residuals).
4. **Identity.** `cal_id = (object_kind, identifier, model_id)`. e.g., `("YIELD_CURVE", "USD_OIS", "kalman_v3")`.
5. **Provenance.** `source_attestations` is a Merkle-style link back to D3. Re-running calibration on the same D3 rows produces the same `(x, P)` (deterministic Kalman). This is replay.
6. **Temporal semantics.** Mutable map. **Snapshot history kept inside D4 as time-keyed checkpoints** at observation cadence. NOT versioned-append-only like D1, because the parameters truly mutate; we keep checkpoints to enable replay, not to present a versioned semantics.
7. **Failure consequences.** Loss of CalibrationState = pricing DAG leaves go FAILED; FSM cascades to STALE; rebuild by replaying D3 attestations through Kalman. Recovery time is `O(history-length / observations-per-second)`. The framework MUST tolerate this gracefully because vendor outages and Kalman re-initialisations are routine.

**(a) Delete test.** Delete the per-checkpoint `P` covariance matrix (keep only `x`)? No - innovation gating and the consensus protocol (v1.0 sec 4.7) need `P`. Delete `source_attestations`? No - this is the only thing that distinguishes a calibrated parameter from a magic number. Minimum is the full set above.

**(b) LoC budget.** Kalman predict-update is **40 lines** of linear algebra. The map and checkpointing layer is another **30**. Sevent lines for innovation gating. **~80 lines total** for a working calibrator per object kind.

**(c) Worst over-engineering pattern.** Conflating D4 with D3 ("market data" as one giant table that holds both raw quotes AND calibrated curves) - this is what every legacy risk system does. The result is that you cannot tell whether a number is observed or inferred, replay becomes ambiguous, and the no-arbitrage projection has nowhere to live. **Keep them separate. Raw is raw. Calibrated is calibrated. The arrow from D3 to D4 is the Kalman filter and nothing else.** Second worst pattern: a "model parameter store" with hand-typed schemas per model (Heston has 5 fields, SABR has 4, ...) - replace with `x: Vector` and a single `model_id` discriminator. The model code interprets the vector. The store does not.

---

## D5. UnitStatus

1. **Canonical name.** `UnitStatus[u]` -> `UnitStatus`. Per StatesHome ruling.
2. **Definition.** The shared, mutable per-unit state that every holder dereferences identically: lifecycle stage, last settlement price/date, current strategy weights, NAV index, triggered-barrier flag, superseded-by pointer.
3. **Minimum field set.** `lifecycle: Enum`, `last_observed: Map[ObservableKey, (value, t)]`, `superseded_by: Option[UnitId]`. Three fields. Note: I have collapsed `last_settlement_price`, `last_settlement_date`, `current_weights`, `nav_index` into a single `last_observed` map keyed by what the smart contract published. This is product-polymorphic by convention, not by schema.
4. **Identity.** Keyed by `unit_id`. Total at registration (C5 + C7).
5. **Provenance.** Each entry of `last_observed` carries the publishing TransactionId from D7. The lifecycle field's last writer is in D7's move metadata.
6. **Temporal semantics.** Mutable in place. **Time travel reconstructs UnitStatus by replaying D7 from registration** to target time - it is a fold of the move stream. The stored map is a cache.
7. **Failure consequences.** Loss of UnitStatus = lifecycle queries return UNKNOWN; valuation FSM loses repricing triggers; **fully reconstructible from D7**. Outage, not corruption.

**(a) Delete test.** Delete the entire D5 map and rebuild from D7 every time? Yes, conceptually - but at scale this is too expensive on hot paths (every settle reads `last_settlement_price` to compute VM). Keep D5 as a read cache, and verify it as a fold-fixpoint of D7 in property tests. Do not treat it as a primary record. **Cache, not source of truth.**

**(b) LoC budget.** Map + replay-from-D7 builder. **30 lines.** The schema is one struct.

**(c) Worst over-engineering pattern.** Treating UnitStatus as the canonical record (with D7 as a "log") and writing migrations whenever a new lifecycle field appears. Wrong direction. D7 is canonical. UnitStatus is computed. New lifecycle fields are new keys in `last_observed`, not schema migrations.

---

## D6. PositionState

1. **Canonical name.** `PositionState[(w, u)]` -> `Option[PositionState]`. Per StatesHome C1.
2. **Definition.** Per-(holder, unit) economic state that two different wallets can carry distinct values for: accumulated cost, HWM, entry NAV, accrued fees, mandate-breach flags, ccp-binding.
3. **Minimum field set.** Polymorphic per product. The frame: `Option[Map[FieldKey, Decimal | Json]]`. The fields are declared by the smart contract and enumerated in `FIELD_SPEC` (StatesHome C11) which assigns each field its unique writer handler. Examples: `ac` (futures), `hwm` (mandate), `entry_nav` (QIS subscription), `accrued_mgmt_fee` (managed account).
4. **Identity.** `(wallet_id, unit_id)`. Compound key. Option-typed accessor: None means "never held"; Some(zero) means "held once, currently flat."
5. **Provenance.** Each field's last-writer TransactionId in D7 metadata. Per StatesHome C11, exactly one handler class is permitted to write each field.
6. **Temporal semantics.** Monotone carrier (rows never deleted; close-out leaves a zero row). Updates are atomic StateDeltas that cross D1, D5, D6 in one shot (C3). Fold over D7 reconstructs at any t (P3, P8).
7. **Failure consequences.** Loss = catastrophic for any holder who has open positions in path-dependent instruments. **Reconstructible from D7** because every mutation is a move + StateDelta in the log. Recovery time is the cost of replaying every transaction; in practice mitigated by periodic snapshots that are themselves D7 entries (snapshot-as-transaction).

**(a) Delete test.** Per StatesHome adversarial review: nothing here is removable without losing economic facts (HWM, accumulated_cost, mandate breach flags) that are demonstrably per-(w,u). Cannot collapse to per-u (Karpathy substitution test fails) and cannot collapse to per-w (C12 / multi-mandate counterexample). The schema IS the minimum.

**(b) LoC budget.** Map-of-maps + the FIELD_SPEC dispatcher + the StateDelta validator. **80 lines.** The reference impl in StatesHome addendum sec 9 fits in 30 lines because it does not check FIELD_SPEC; production needs the explicit handler-tag check.

**(c) Worst over-engineering pattern.** A "positions table" with one column per product type (futures_ac, qis_hwm, managed_account_fee, ...) - the v10.3 sec 7 line 1034 phrasing leaks toward this. StatesHome C12 explicitly forbids it. Use the polymorphic field-map; let the smart contract's FIELD_SPEC be the schema.

---

## D7. MoveStream

1. **Canonical name.** `MoveStream` -> append-only sequence of `Transaction`.
2. **Definition.** **The canonical record of the framework.** Every economic event - trade, settle, lifecycle, corporate action, registration, KYC update - is a Transaction in this stream. Every other data category in this enumeration (D1, D5, D6, D8, D9) is a fold projection of D7. The proposed floor categories omit this; that is the most serious error in the proposed taxonomy.
3. **Minimum field set per Transaction.** `tx_id` (hash), `t_logical: Timestamp` (event time per CDM payload), `t_committed: Timestamp` (executor commit time), `type: SETTLEMENT | COLLATERAL | LIFECYCLE | ACCOUNTING | CORRECTION` (per v10.3 sec 9.3), `moves: List[Move]`, `cdm_payload: Json`, `prev_hash: Bytes` (chain), `signature: Bytes`. Per Move: `(src, dst, unit, qty, metadata)`. Eight fields per Tx, five per Move.
4. **Identity.** `tx_id = hash(prev_hash, payload_canonical)`. The chain is the Merkle structure; tamper-evidence by construction (Invariant 4).
5. **Provenance.** Self-provenancing: every transaction carries the CDM event that originated it.
6. **Temporal semantics.** **Append-only, hash-chained, bitemporal.** `t_logical` for time-travel queries; `t_committed` for audit. Never mutated.
7. **Failure consequences.** Loss of D7 = total loss of the framework. **D7 is the only category for which loss is unrecoverable from anything else inside the system.** Backups are mandatory; the spec calls for WORM/HSM (Invariant 4 in v10.3 sec 11.2). Every other category can be rebuilt from D7; D7 cannot be rebuilt from any of them.

**(a) Delete test.** Delete `t_committed`? No - audit demands it (when did we know). Delete `cdm_payload`? Catastrophic - this is the input that makes replay deterministic and that re-creates D1 if necessary. Delete `prev_hash`? Cryptographic guarantee gone; tamper-evidence reduced to "trust the database." Minimum is the full set.

**(b) LoC budget.** Append + hash-chain + signature verify + idempotent dedup by tx_id + atomic commit semantics. **120 lines** including a basic snapshot mechanism. This is the highest-value 120 lines in the codebase.

**(c) Worst over-engineering pattern.** Treating D7 as "an event log on the side" while another database holds "the real positions." This is the standard Kafka-plus-OLTP pattern, and it is wrong here: in an event-sourced ledger, the log IS the database. Positions are folds. Anyone who introduces a separate "positions DB" with a sync-from-log job has imported a class of bugs (drift, consistency-window, dual-writes) that the architecture explicitly closes (Invariant 4 + C2 + C3). Second worst: per-tx XML/JSON schemas for vendor interop - keep the canonical form simple, do interop at the projection layer (D8 + settlement.sese.023).

---

## D8. ValuationRecord

1. **Canonical name.** `ValuationRecord[(u, t, model_id)]`.
2. **Definition.** Per (unit, time, model) the dirty price + Greeks + quality + FSM state. Per valuation v1.0 sec 3.
3. **Minimum field set.** `unit_id`, `t`, `model_id`, `dirty_price: Decimal`, `greeks: Vector[Decimal]` (model-polymorphic per Jacobian), `quality: FIRM | INDICATIVE | APPROXIMATE | STALE | FAILED`, `attestation_snap: SnapshotId` (which D3+D4 rows fed it), `fsm_state: ValuationState`. Eight fields.
4. **Identity.** `(unit_id, t, model_id)`.
5. **Provenance.** `attestation_snap` links back to D3 + D4. This is what makes PnL explain reproducible (see D8(c) below).
6. **Temporal semantics.** Append-only per (unit, t, model). Latest-FIRM is a query, not a state.
7. **Failure consequences.** Loss = repricing rebuilds it from D3 + D4 + D6 + D1 deterministically (per Edge Case 4: MC determinism via seeded hash). No economic data is lost; outage only.

**(a) Delete test.** Delete `clean_price` and `accrued`? Yes - both are derivable from `dirty_price` and the unit's accrual state in D5. Delete `compute_ms`? Yes - that is observability, not data; ship to Prometheus/OpenTelemetry, not to the valuation store. The five fields v1.0 sec 3 lists in addition to my eight (`clean_price`, `accrued`, `model_id` is kept, `market_data_snap` becomes `attestation_snap`, `compute_ms`) reduce to one (clean_price/accrued are derived).

**(b) LoC budget.** Insert + index + `snapshot_at(t)` query. **40 lines.**

**(c) Worst over-engineering pattern.** A "pricing warehouse" that stores every Greek for every model for every unit at every cadence boundary, indexed eight ways, with retention tiers. Wrong: prune aggressively. Keep last-FIRM per (unit, model) hot, archive the rest, recompute on demand from D3+D4. The valuation v1.0 spec already says "official PnL uses FIRM only" - the rest is a cache. Second worst: storing one schema per pricing model (Heston schema, SABR schema, BlackScholes schema, ...). Use `greeks: Vector` with a `model_id` discriminator; the consumer of the Vector knows the order.

---

## D9. ObligationStore

1. **Canonical name.** `ObligationStore[obl_id]` -> `Obligation`. Per v10.3 sec 14.7.
2. **Definition.** Pending discharge requirements (CSA margin calls, SBL recalls, settlement obligations) with deadlines and discharge predicates. The liveness companion to safety. Without this category, the framework provably cannot prove margin discharge.
3. **Minimum field set.** `obl_id`, `kind: Enum`, `created_by: TxId` (the transaction that registered the obligation), `deadline: Timestamp`, `discharge_predicate: PredicateRef`, `compensation_handler: HandlerRef`, `status: PENDING | DISCHARGED | COMPENSATED`. Seven fields.
4. **Identity.** `obl_id = hash(created_by, kind, deadline)`.
5. **Provenance.** `created_by` links to D7. Discharge or compensation are themselves D7 transactions; status updates flow from D7 events.
6. **Temporal semantics.** Monotone carrier with a closed terminal state. Once DISCHARGED or COMPENSATED, the row is frozen (audit trail).
7. **Failure consequences.** Loss = liveness loss; safety unaffected. Margin calls go un-chased; SBL recalls do not cascade. Reconstructible from D7 if every obligation registration was a transaction (which the spec mandates - sec 14.7 "Obligation Registration").

**(a) Delete test.** Could obligations live in D5/UnitStatus instead? No - they are per-(holder, counterparty) commitments, often spanning multiple units (CSA), and have their own lifecycle distinct from any one unit's. They earn their map.

**(b) LoC budget.** Map + Temporal-timer integration + predicate evaluator. **60 lines** for the store (the timer infra is Temporal's, not the spec's).

**(c) Worst over-engineering pattern.** A workflow engine pretending to be an obligation store (every obligation is a Temporal workflow with a timer attached, status fields scattered across workflow internal state). Per v10.3, the obligation IS data; Temporal merely fires the timer. Keep the data in D9, keep the timing in Temporal, never conflate. Second worst: per-regulation obligation kinds (an EMIR-margin-obligation type, an SLATE-obligation type, ...) - the kind enum should reflect *what discharge requires*, not *which regulator cares*.

---

## What I would still delete

Even after the consolidation above, three patterns still concern me:

1. **D5/UnitStatus shrinking further.** `lifecycle_stage` could be a tag on the latest D7 transaction with `metadata.kind == LIFECYCLE` - read by query, not stored as state. The cost is one query per pricing call; the gain is one fewer mutable map. I would benchmark.
2. **D8/ValuationRecord caching only.** The valuation store is an aggressive cache of a pure function. In a ruthless rebuild I would not give it its own category and would store nothing - rebuild on every read from D3+D4+D5+D6+D1. The cache exists because that compute is expensive at scale; do not let the cache pretend to be a primary record.
3. **Reference data that is not unit terms.** Things like business-day calendars, holiday tables, day-count conventions. These are pure functions of `(jurisdiction, date)`. They are *code*, not data. Embed them in the smart contract library. The framework does not need a "calendar table." If you find yourself building one, you have made a mistake.

## What I would refuse to add

The following candidates appear in real-world peer systems but should NOT enter this enumeration:

- **A "Trade" table.** A trade is a Transaction in D7. There is no separate trade entity.
- **A "Position" table.** A position is `apply(D7)` projected on a wallet. There is no separate position entity. Positions are computed.
- **A "Risk" table.** Risk is a query over D6 + D8. There is no separate risk record.
- **An "Account" table.** An account is a Wallet (D2) plus the positions implied by D7. The settlement layer maps wallets to external accounts; that is a separate system.
- **A "PnL" table.** PnL is `V_t1 - V_t0`. It is a computation, not a stored fact. Per the path-independence theorem (v10.3 sec 4.3), storing it is redundant and breaks invariance under intermediate-state changes.

If a category does not survive the question "could you compute this from D1..D9 in O(1) amortised at query time with reasonable engineering?", it is not a primary category - it is a materialised view, and it should be treated as such (rebuilt deterministically, not stored as truth).

---

## Summary count

- **Categories enumerated:** 9 (D1-D9).
- **Floor categories collapsed:** 6 -> 4 effective categories (Static+Reference -> D1; Market split into D3+D4; Oracle subsumed into D3; Smart-contract execution merged into D7; Listed-instrument detail rejected as a category).
- **Categories added beyond the floor:** D7 (MoveStream - the most important), D8 (ValuationRecord), D9 (ObligationStore), D2 (WalletRegistry per StatesHome).
- **Most aggressive deletions argued:** the entire "tier 1/2/3" structure of v10.3 sec 3.3; the implicit "trade/position/PnL" tables; vendor-typed market data schemas; lifecycle_stage as stored state; per-model-typed Greek tables.
- **Single most important assertion:** **D7 is the canonical record. Everything else is a fold.** Any data spec that does not start there is solving the wrong problem.
