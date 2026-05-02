# R1 Review — Jane Street CTO

## Verdict
**REQUEST CHANGES**

The architecture is largely sound and the boundary discipline is correct. But the load-bearing artefact — §3 — has a conservation table that does not balance under v10.3's own definition of `Q(u)`, the recon identity in §4.1 silently re-introduces non-ledger state (`inflight_in/out`), and the type-discipline migration plan is fiction. These are fixable. The thesis is right; the execution has soft spots that will bite the on-call engineer at 3am.

## Blocking issues

### B-1 — §3.6 conservation tables do not satisfy v10.3 P1
The USD table (lines 321–327) shows `Σ_internal = 1,000,000` at every horizon. By v10.3 §2 conservation, `Q(u) = Σ_{w ∈ W} w_t(u) = 0` over **all** wallets (real + virtual). Summing the four columns directly:
- T⁻: 1,000,000 + 0 + 0 + 1,000,000 = **2,000,000** ≠ 0 (and ≠ the 1,000,000 the table claims)
- T+2⁺: 995,000 + 0 + 5,000 + 995,000 = **1,995,000** ≠ 0

The table is implicitly excluding the nostro wallet from `Σ_internal`, which is fine as a *projection*, but it is then **not** the conservation law. A worked example explicitly invoked by §2.6 ("PS/PSS wallets are full participants in W_virtual; no conservation carve-out") MUST close to zero — that is the whole point of the closed-system framing. As written, a reader cannot tell whether the missing -1,000,000 contra (the issuer/Federal Reserve virtual wallet that mirrors all USD in the system) was simply omitted for brevity or whether the framework is leaking conservation. v10.3 §2 lines 206–239 require the issuer-virtual contra; the example does not show it.

**Why it blocks.** Section 3 is "the load-bearing concrete artifact. Every other section in this proposal refers back to this block." If the canonical example does not satisfy the canonical conservation law, every downstream property test is anchored on shifting sand. The XYZ table balances trivially because XYZ starts at zero (no pre-existing position) — but the framework MUST handle pre-existing inventory.

**What unblocks.** Add the issuer-virtual contra rows. Make `Σ_w` truly span all wallets and equal zero at every horizon. State explicitly which column is the closed-system invariant and which is a projection. If `Σ_internal` is intentionally a proper sub-sum, name it (`Σ_W_real ∪ W_PS ∪ W_broker`) and state what it equals (it equals `−nostro_external`, a non-zero invariant of an open subsystem — fine but say so).

### B-2 — §4.1 recon identity smuggles `inflight_in/out` in as if they were ledger state
The identity is:
```
nostro_external = own + Σ PS_payable − Σ PS_receivable − inflight_out + inflight_in
```
The two `inflight_*` terms are not defined anywhere in §2 (the state-representation section). They are not PS/PSS balances. They appear in §2.3's wallet-class enumeration as `virtual_inflight_out` and `virtual_inflight_in` and then never explained. This is the exact trap §1's "what was rejected" passage congratulates the team for avoiding ("storing them duplicates state and reintroduces 'where does the contra live?' trap"). Yet here they are.

If `inflight_out` is a wire that has left our nostro but JPMC hasn't acked the destination yet, that is a real operational state. But then the proposal owes:
1. A wallet definition (where does the balance live? what's the constructor?)
2. A handler (which event mutates it?)
3. A discharge predicate (which witness drains it?)
4. A conservation argument (its contra-wallet)
5. Inclusion in §3's worked example

None of these are present. The §4.4 morning-recon report shows `−inflight_out` and `+inflight_in` as separate lines that don't map to any wallet defined in §2.

**Why it blocks.** The reconciliation identity is the spec's central operational claim. If two terms in it are undefined ledger state, the identity is not implementable as written. The recon engineer chasing a $13.42 break has no row to point at.

**What unblocks.** Either (a) collapse `inflight_*` into a fifth virtual-wallet pair (e.g., `WIRE_inflight[w, ccy]` with explicit semantics, handler, witness) and update §3.6 to show its lifecycle, or (b) prove that `inflight_*` is zero whenever `nostro_external` has been refreshed and remove the terms. Option (a) is the right call — wires fail and JPMC takes hours to ack — but commit and document it.

### B-3 — §4.3 "constant-time" SQL claim is wrong
The query is grouped over PS/PSS rows for the wallet. Cost is `O(open_counterparties × open_currencies × wallet_classes_filter_factor)`, *not* constant. The claim "no join to MoveStream, no replay over open-instruction set" is true — and that is the actual win. Don't oversell it. At 10^7 trades/day with even a moderate counterparty count, "dozens to hundreds" of open counterparties per real wallet underestimates the long tail (think regional brokers, dark-pool MMs, agency lots, allocation chains).

**Why it blocks.** The proposal sells the recon engine as "constant-time per (w, ccy)" and a downstream operations team will wire SLAs to that. It isn't constant-time; it's `O(N_cpty)` with a small constant. Quantify it correctly: at 10^4 wallets × 10^3 cpty × 10^2 currencies = 10^9 worst-case tuples, the recon scan must beat 5 minutes on real hardware. That's a different engineering problem than the spec implies.

**What unblocks.** Replace "constant-time" with explicit complexity bounds and a concrete throughput target benchmarked on representative data. State the indexing requirement (`(real_wallet, wallet_class, ccy)` covering index, partial on `wallet_class IN ('virtual_PS_*')`). Add a stress-test acceptance criterion in §15.

### B-4 — Per-leg FSM × 10^7 trades/day storage reality unaddressed
§5.2 commits per-leg `L_15.Obligation` rows. DvP = 2 rows; cross-currency DvP = 3 rows; SBL with collateral = 3-4 rows. At 10^7 trades/day this is **2-4×10^7 obligation rows/day**, ~10^10/year, with the bitemporal structure (DS16) requiring all corrections appended, not in place. The §10 audit retention is 7 years. That is ~10^11 rows in the obligation store before allocation chains, partial-settlement child obligations (DS11 with D_max=2 doubles in the worst case), and CSDR_PENALTY rows (one per failed leg per day).

The proposal contains zero discussion of:
- Storage tier (hot/warm/cold)
- Index strategy (which queries are realtime vs batch)
- Partition strategy (by `intended_settlement_date`? by `cpty_lei`? by `ccy`?)
- Cost — at $0.02/GB-month at modest density this is a 7-figure annual line

**Why it blocks.** "Implementable by a small team in finite time" needs a storage answer or the team will stall in week 8. This isn't a fatal architectural flaw — it's a sizing exercise — but it must be done before commitment.

**What unblocks.** A one-page operational annex: row-size estimate, daily volume, partition scheme, retention tiering, a back-of-envelope cost. Pin partitioning by `(intended_settlement_date, cpty_lei)` is my recommendation: aligns with recon scan keys, makes "drop the oldest tier" trivial, supports the morning-recon hot-path.

### B-5 — Deterministic tx_id collides under high-frequency flow
§3.2 specifies:
```
tx_id = hash("ECON_REC", "BUY", "XYZ", 100, 50.0000_0000, GS_LEI, "2026-04-30T14:32:11Z")
```
At 1-second timestamp resolution, two identical buys at 14:32:11 (e.g., a 100-share child-order pair from the same VWAP slicer) collide. §6.4 mentions an `attempt_seq` field "in the deterministic tx_id formula" but it is not present in §3.2 and not defined as part of the canonical hash recipe. PO-10 commits temporal to "tx_id derivation must NOT include run_id" but does not pin the actual ingredients.

**Why it blocks.** Λ10 (content-addressing) is foundational to the entire idempotency story (DS6, P5, the entire ingest pipeline). A collision means two distinct economic events get conflated in the move stream. This is a P0 correctness bug.

**What unblocks.** Pin the tx_id ingredient list in one canonical recipe in §3 or §5. It must include: `(business_event_id, attempt_seq, source_seq_no_from_OMS, micro/nanosecond timestamp)`. State the hash function, the canonicalisation discipline (JCS — already mentioned for UTI), the collision-probability bound. Property test: 10^9 random trades, no collision.

## Unmitigated major issues

### M-1 — `PositionState[w_PS, u].own` conflates GPM coordinate with scalar balance
The proposal repeatedly writes balances on PS/PSS virtual wallets as `PositionState[w_PS, u].own` (e.g., §2.1 row 2; §2.5 column 3; §3.2 conservation table). But `own` is the **first coordinate of the GPM 6-tuple** (v10.3 §13: `(own, onloan, borr, coll_post, coll_recv, coll_rehyp)`), defined for real wallets carrying lendable instruments. PS/PSS wallets are scalar contras for `(cpty, ccy_or_ISIN)`. They neither lend nor borrow nor pledge collateral.

Two readings, both wrong-flavoured:
- (a) PS/PSS wallets carry a degenerate 6-tuple where 5 coordinates are pinned to zero. Then *every* PS/PSS row pays the storage cost of 6 fields for 1 real bit. Cardinality blow-up + a meaningless schema.
- (b) PS/PSS wallets carry a scalar — but then the PositionState schema is now polymorphic over wallet_class, which the StatesHome canonical 3-map ruling does not contemplate (StatesHome §1: `PositionState : Map[(WalletId, UnitId), PositionState]` is one type).

The proposal says it is reusing existing v10.3 storage with "zero new fields on PositionState." But the v10.3 PositionState fields per StatesHome are `accumulated_cost`, `ccp_binding`, `entry_nav`, `hwm`, `accrued_*_fee`, `mandate_breach_flags` — none of which is `own`. The `own` reading only makes sense if PS/PSS wallets sit in the GPM extension's PositionState, which is itself a schema decision Phase 2 has not actually taken.

**Why this is major, not blocking.** Implementations can finesse it — most likely by giving PS/PSS wallets a degenerate scalar tag and routing reads through the same accessor. But the spec must say so or six different teams will solve it six different ways. **Pick one and pin it.** I recommend a separate `BalanceCarrier` type with `wallet_class` discriminating between scalar (PS/PSS, depot, nostro) and 6-tuple (real GPM-bearing) — this is honest about what the system is.

### M-2 — 18 invariants is too many; folds are obvious
DS3 (recon identity) and DS13 (recon pair anchoring) are the same invariant at different cadences. DS5 (replay determinism) and DS6 (idempotency of finality) are the same property — idempotency of singletons is the base case of replay-determinism on multisets. DS9 (buy-in closure) is a special case of DS15 (close-out routing) restricted to the CSDR/Reg-SHO regime. DS14 (CSDR penalty schema determinism) is a corollary of DS5+DS17 specialised to the penalty-rate-table reader.

Load-bearing core: DS1 (economic exposure), DS2 (conservation), DS3 (recon identity), DS4 (no discharge without witness), DS7 (failure non-reversal), DS8 (status monotonicity), DS17 (capability scoping), DS18 (DvP atomicity). **Eight invariants** carry the weight. The other ten are restatements, corollaries, or operational aspirations.

**Why this matters.** The TLA+ check at PO-8 (`|W|=3, |U|=2, depth=8`) with 18 invariants encoded will spend most of its state-space budget proving redundancies. Eight tight invariants verify faster, fail more informatively when violated, and are what the formal review actually has to defend.

**Recommendation.** Designate the 8 above as MANDATORY. Demote the rest to "derived properties" with proofs from the 8. The TLC run encodes only the 8.

### M-3 — Type discipline migration "14 weeks, 1-2 engineers" is fantasy
§12.9 sketches a migration that introduces:
- Phantom-typed wallet handles (every call site with a `wallet_id` parameter)
- Closed-sum lifecycle FSM with carried evidence (every read/write of `lifecycle_stage`)
- Newtype dates for `TradeDate`, `SettleDate`, `ValueDate`, `RecordDate` (every settle-date arithmetic site)
- `PairedObligation` with smart-constructor `pair` returning `Result.t` (every discharge call site)
- `Obligation.create` smart constructor rejecting 14 malformed cases (every obligation issuer)
- 6 new compile-time invariants

Anybody who has done a refactor of comparable scope on a tier-1 trading codebase knows this is **engineer-quarters, not engineer-weeks**. The proposal does not mention:
- Number of existing call sites (probably 10^3-10^4 for `lifecycle_stage` alone)
- Existing test surface that must be migrated alongside
- Backward compatibility with persisted state (the bitemporal store has years of `lifecycle_stage : string` rows)
- The CDM 6.0 deserialisation boundary (CDM gives strings; the boundary needs adapters)
- Build system / CI cost of `-warn-error +partial-match` across the whole tree

**Why this is major.** A spec that promises a migration in 14 weeks and delivers in 14 months erodes trust. Scope it honestly: 6-9 engineer-months for the type-additive stages 1-4; stages 5-6 are best-effort cleanup over a quarter or two.

**Recommendation.** Replace the table with a phased plan whose Stage 1 is "introduce types behind a feature flag, no production cutover" with a 6-month horizon. Pin Stage 2 cutover criteria (test coverage, replay-equivalence on 90 days of production data, performance regression < 5%). Drop the engineer count or honestly state "a senior team for a quarter."

### M-4 — `w_GS_broker` semantics are wrong (or under-specified)
§3.5 post-finality: `w_GS_broker.own(USD) = +5,000`. The interpretation: "we know GS received $5,000." We do not. We know JPMC debited our nostro and that the SSI on the sese.023 routed to GS's bank. The fact that GS *actually received* the wire is a separate witness (an MT900/910 or a counterparty confirmation) that may or may not arrive.

This matters because:
- The conservation argument requires `w_GS_broker` to mirror "GS's actual position" — but our ledger cannot observe GS's bank.
- A wire-recall scenario (we instruct JPMC to recall before the beneficiary bank credits GS) leaves the cash mid-flight; `w_GS_broker.own(USD) = +5,000` is wrong.
- The Herstatt window analysis in §10 depends on per-leg discharge witnesses; the cash leg's discharge-witness is `camt.054` (debit notification on our nostro), not "GS received."

**Why this is major.** The framework's own §1 thesis says "Ledger represents *what we promised* (the obligation, with discharge predicate); settlement utility provides *how the promise is mechanically discharged*." Then `w_GS_broker.own(USD) = +5000` is not an attested fact; it's a presumed mirror. Either (a) re-read it as "the cash leg of the obligation has been debited from our nostro per `camt.054`; the broker virtual wallet records the contra of that debit," or (b) admit that the broker virtual is a presumption that breaks under wire-recall and partial-credit scenarios.

**Recommendation.** Rename the contra in §3 examples to make it clear it is *our debit's contra*, not GS's actual receipt. Something like `w_GS_settlement_contra` with a doc-string: "the contra of the nostro debit observed on `camt.054`; not GS's confirmed credit." If GS's actual receipt matters (e.g., wire-recall), introduce an explicit `w_GS_attested_received` with its own discharge witness.

### M-5 — Late corrections / retroactive amendment story is incomplete for the cross-correction case
§10.9 covers append-only CORRECTION transactions for the local case (we booked wrong). G5 covers the case where the CSD restates a prior confirmation. But the framework does not address:
- We CORRECT a trade that has already been MiFIR-reported (T+1). The L_17 row's TR ack is now anchored to a now-reversed economic event.
- A counterparty disputes a trade we have already settled (rare but it happens — DTCC dispute resolution). The "mutual bust" path requires both parties to issue a CORRECTION; what if only one does?
- A CORRECTION is itself wrong and needs un-correcting. §10.9 says correction-of-correction is "NOT permitted" — but the only way to repair a wrong correction in an append-only log IS another correction. This is internally inconsistent.

**Recommendation.** Three explicit playbooks (regulatory-already-reported; one-sided dispute; CORRECTION-of-CORRECTION) in §10.9 or §13. Acknowledge that "no correction-of-correction" is a doctrine, not a mechanism — the mechanism remains a third CORRECTION, and the doctrine is to require explicit governance approval to author one.

### M-6 — Manual override / golden-source disagreement is absent from the FSM
DS4 ("no discharge without witness") is correct as a default. But production reality includes:
- CSD's `sese.025` says settled-100; the depot statement next morning says 99. Which wins?
- Counterparty insists they delivered; we have no `sese.025`. Manual reconciliation eventually agrees they did. How does the obligation transition?
- The CSD is down for an outage; we know operationally that settlement happened (e.g., bilateral confirmation by phone, signed faxes). How is this booked?

§14 explicitly punts CSD outages to a future revision. But manual override is not a CSD-outage problem — it is a daily occurrence in any settlement shop. The framework needs a `MANUAL_DISCHARGE` witness type that requires four-eyes (parallel to CORRECTION's discipline) and that is structurally distinguished from cryptographically verified CSD attestations.

**Why this is major.** Without it, every production exception will exit the framework via an undocumented CORRECTION transaction, which collapses the auditability story.

**Recommendation.** Add an explicit `ManualAttestation` envelope type with four-eyes, named approver role, mandatory justification, and a flag `attestation_class ∈ {CRYPTOGRAPHIC, MANUAL}` on the L_15 discharge_witness. DS4 is preserved (a witness exists); the witness's quality is named.

### M-7 — Block-and-allocation chains absent from the spec
A block trade for 100,000 XYZ executes at T against broker B; allocations to 12 sub-funds are agreed at T+0 evening; sub-funds settle to their respective custodians at T+2. This is the dominant flow shape for asset managers. The spec mentions "block-and-allocation chain reconciliation" as a recon cadence (§4.7) but does NOT specify:
- Is the block one obligation that splits into 12, or 12 obligations from inception?
- What is the recursion bound D_max for allocation depth (vs. partial-settlement depth)?
- How does PSS_payable[w_block, B, XYZ] decompose into 12 sub-fund-keyed PSS rows?
- Allocation-revision (a sub-fund pulls out at T+1) — how is the obligation graph mutated?

**Recommendation.** Treat allocations as a separate worked example in §3 (parallel to §3's standard buy). It is a different structural pattern, not a corner case.

## Minor issues

### m-1 — §2.1 row 2 says PS/PSS wallets are "Writer (C11 cap): apply_trade_move at T (initial credit/debit); same handler at T+N (drain)"
But §3.5 finality is a different transaction kind (`SETTLEMENT_FINALITY`) emitted by `SettlementWorkflow`, not `apply_trade_move`. The C11 capability table needs row 2 split into "writer at T = apply_trade_move" and "writer at T+N (drain) = settlement_finality_handler." Otherwise C11 (capability scoping) cannot be enforced; both handlers would need the same capability tag.

### m-2 — §3.7 PnL math anchors at 1.00 USD but trade was on 14:32 timestamp
The PnL formula `V_{T+1} = w.own(USD) × P_{T+1}(USD) + w.own(XYZ) × P_{T+1}(XYZ)` uses `P_{T+1}(USD) = 1.0000`. Fine for a USD-base book. State the base currency assumption explicitly; reviewers in JPY base will be confused.

### m-3 — §6.3 CSDR penalty obligation_id derivation
`hash("CSDR_PENALTY", refers_to_tx, intended_settle_date)` does not encode the failing party. If a DvP fails on the securities leg only (we receive cash, fail to deliver shares), the failing party is us. If both legs fail, two penalty obligations exist (each leg's failing party). The hash recipe needs `failing_party_lei` to disambiguate.

### m-4 — §7.3.2 sign of PS_receivable for cash on a sale
"PS_receivable[w_C, D, USD] = -50000 (D paid us; symmetric mirror)." The negative sign is consistent with §2.7's "PS_receivable holds cash arriving" and with the §3.2 example's sign convention only if the convention is "PS_receivable balance is positive on amounts NOT yet received." Pin the sign convention in one canonical sentence in §2; right now it is implicit in three different examples.

### m-5 — §11 DS8 statement says retrograde edges are allowed (Failed → Instructed) but §5.3 transition table only allows `FAILED → SETTLED` (post buy-in). DS8 wording allows re-instruction after fail; §5.3 does not. Pick one. (Re-instruction post-fail is correct operationally — partial-fill sequel — so §5.3 should match DS8.)

### m-6 — §11 DS5 typing as "RT — property-test (multi-permutation replay)"
This is by far the highest-leverage property test in the spec (it underwrites the whole out-of-order-finality story). It needs more than a one-line entry. Specify: number of permutations to test (factorial-bounded for small `n`, sampled for large), depth of confirmation streams, the equivalence relation tested (state-equality on `(L_13, SettlStatus, L_15)` after fold). This is the test that catches the bug everyone writes once.

### m-7 — §12.5 smart constructor case 5 (`|qty × price − cash_amount| > rounding_tolerance(currency)`)
This implicitly requires the constructor to know the price, but obligations are issued at trade time when price *is* known. Fine. But for FX-funded trades, the cash leg's notional may be in a different currency from the price's currency — the constructor needs `(qty, price, price_ccy, cash_amount, cash_ccy, fx_rate, fx_pin)`. Otherwise this rejection is unsound.

### m-8 — §15 Pareto-arbiter open items are ducked, not closed
"Per-counterparty vs per-instruction PS/PSS keying" is parked. The proposal de facto adopts per-counterparty (§2.2) but §15.2 says the choice is "not formally decided." Pick one and own it. Per-counterparty is the right call for v11.0 (matches recon scan keys; per-instruction is recoverable as a join). Make the call.

## What works well

- **The boundary between Ledger and settlement utility is clean** (§1 thesis). "Ledger represents what we promised; settlement utility provides how the promise is discharged" is the right mental model. The rejection of "settlement state purely external" and "settlement state on UnitStatus[ISIN]" in §1 is correct and well-argued.
- **Per-leg L_15 obligations** (§5.2) is the right call over per-transaction. The half-failed DvP case is real, common, and not representable any other way. Don't backslide on this even when the storage cost (B-4) bites.
- **§7.4 recall-during-window** is a clean, honest worked example that the field gets wrong constantly. The two obligations are independent; the framework's representation matches GMSLA reality. Keep this.
- **§9.7 tri-regime UTI gotcha and value-date conventions** is the kind of operational detail that prevents real production bugs. Promote this from regulatory-footprint to a first-class warning.
- **§12.2 PairedObligation** is the right primitive for DvP atomicity at discharge time. The fact that it forecloses a single-leg discharge from the type system is exactly the "make illegal states unrepresentable" win that earns the type-discipline cost (modulo M-3's migration timing).

## Recommendation

The architecture is correct; the spec is over-stated in places where production grinds it down. Fix B-1 (conservation worked example), B-2 (define `inflight_*` or remove), B-3 (replace "constant-time" with concrete benchmarks), B-4 (a one-page sizing annex), and B-5 (pin tx_id recipe). Fold the 18 invariants to 8 mandatory + 10 derived. Be honest about the type-discipline migration cost — call it a quarter for a senior team rather than 14 weeks for 1.5 engineers. Add the manual-attestation and block-and-allocation worked examples; production will demand both within the first month. With those changes this is implementable, defensible at audit, and survivable on-call. Without them it ships, runs, and fails quietly the first time a CSD restates a confirmation that was already MiFIR-reported and a CORRECTION needs correcting. Round 2 with these fixes; do not let "implementation-ready" stand on the §3 conservation table as currently written.
