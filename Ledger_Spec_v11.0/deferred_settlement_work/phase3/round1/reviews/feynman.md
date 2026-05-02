# Round 1 Adversarial Review — feynman

**Target:** `proposal_v1.md` (Phase 2 Settlement Team unified design, deferred-settlement on cash equities, Ledger v11.0)
**Reviewer:** feynman (Phase 1 dissent on `pending_in/pending_out` as state — accepted as projection, not stored coordinate)
**Discipline:** multiple representations; "what I cannot create I do not understand"; "the first principle is you must not fool yourself"

---

## Verdict

**ACCEPT_WITH_CHANGES** — but with **two blocking sign-convention defects** that are load-bearing for DS3 and the entire reconciliation chapter, plus one major path-independence gap on the failed-trade lifecycle that the proposal claims as a property without proving.

The proposal is the most coherent piece of work I have seen since v10.3 §13. The architecture is right: trade-date economic recognition on `own`, virtual PS/PSS contras carry obligation quantities, `L_15` carries the lifecycle FSM, transaction-level status is a projection. The settlement-window-as-parameter framing (DS12) is the test of CDM-native design and the proposal passes it. §3 worked example, §10.2 journal entries, §12 phantom-typed wallet handles, and §11 DS18 (DvP atomicity at the type level via `PairedObligation`) are the load-bearing artifacts and they are largely sound.

But the proposal **explicitly claims to have corrected the Phase 1 sign error in §4.2** while having only verified the buy-side cash leg. The sell-side cash receivable, the buy-side securities receivable, and the SBL composition path all break the §4.1 identity under the storage convention used in §3.2 and §7.3.2. The proposal is fooling itself on the very point that §15.1 lists as known weakness (PO-3) — by claiming both that the sign is fixed (§3.2, §4.2) and that it is open (§15.1 item 1). One of these statements is wrong.

**Multiple-representations test result:** PnL passes (two methods agree, +$200 / -$50 / +$150 cumulative). Recon identity FAILS — verifying §4.1 by independent substitution against §3 storage gives the wrong answer on the securities leg of the buy and the cash leg of a sell. DS3 in §11 has a different shape from §4.1 and the two do not reduce to each other under §3 storage. **The proposal does not pass its own self-consistency check.**

**Stranger test result:** A first-year trained on this would emerge clear on what trade-date accounting is, why DS1 matters, and how DvP atomicity is enforced via the type system. They would not be able to answer "do PS_receivable balances store as positive or negative?" without checking three different sections — the proposal never states the storage sign convention in one place, and the three places that imply it (§3.2 moves, §4.1 algebra, §11 DS3) are not consistent.

---

## Blocking (B-N)

### B-1 — §4.1 reconciliation identity is sign-broken on the receivables side

**Independent computation, securities side at T (post-§3.2 worked-example trade):**

Storage from §3.2 (verified):
- `w_us.own(XYZ) = +100`
- `PSS_receivable[w_us, GS, XYZ].own = -100` (because Move 1 was `from=PSS_receivable, to=w_us, qty=100`, conservation forces -100)
- `PSS_payable[*] = 0`
- `depot_external = 0` (T-day, depot not yet credited)

Substitute into §4.1 securities formula:
```
depot_external = own + Σ PSS_payable − Σ PSS_receivable − depot_out + depot_in
0 ?=  100   +     0       −     (−100)        −     0     +     0
0 ?=  200
```

**Identity fails by 200.** This is not within tolerance; it is structurally wrong by a factor of 2.

**Independent computation, cash side at T for a hypothetical SELL:**

Sell 100 XYZ @ $50 (mirror of §3.2). Storage by §3.2 mirror logic (and confirmed against §7.3.2 short-sale Move pattern):
- `w_us.own(USD) = +1,050,000` (sale proceeds booked at T per DS1)
- `PS_receivable[w_us, GS, USD].own = −5,000` (Move was `from=PS_receivable, to=w_us, qty=5000`)
- `PS_payable[*] = 0`
- `nostro_external = 1,000,000` (JPMC has not yet received D's wire)

Substitute into §4.1 cash formula:
```
nostro = own + Σ PS_payable − Σ PS_receivable − inflight_out + inflight_in
1,000,000 ?= 1,050,000 + 0 − (−5,000) − 0 + 0
1,000,000 ?= 1,100,000
```

**Identity fails by 100,000.** Again structurally wrong.

**The hidden bug:** §4.2 verification only exercises the BUY case where `Σ PS_receivable = 0` on the cash side, so the sign of that term is invisible. The bug emerges the moment a sell, a short, an SBL, or any transaction with a cash receivable enters the recon. §3.2 storage convention combined with §4.1 algebraic form produces a wrong recon for half of the framework's transaction taxonomy.

**Two correct alternatives, pick one and document explicitly:**

1. **Flip the algebra:** `nostro = own + Σ PS_payable + Σ PS_receivable − inflight_out + inflight_in`. Storage stays as written in §3 / §7. Receivables stored as negative (their additive contribution is automatically subtractive). Verification:
   - Buy at T: `1,000,000 ?= 995,000 + 5,000 + 0 − 0 + 0 = 1,000,000` ✓
   - Sell at T: `1,000,000 ?= 1,050,000 + 0 + (−5,000) − 0 + 0 = 1,000,000` ✓
   - Securities buy at T: `0 ?= 100 + 0 + (−100) − 0 + 0 = 0` ✓

2. **Flip the storage:** `PS_receivable` stored as positive when "they owe us"; the §3.2 Move pattern needs to invert. Then §4.1 algebra (`− Σ PS_receivable`) is correct as written. This is more work because §3, §6.4, §7.3.2 all need rewriting, and the asymmetry between payable Moves (`from=w_us, to=PS_payable`) and receivable Moves (`from=PS_receivable, to=w_us`) is deeply baked in.

**Recommendation:** Alternative 1. Net change: change the two minus signs in §4.1 (cash and securities formulae) to plus signs. Re-verify §4.2 with both BUY and SELL examples. Update DS3 in §11 to match.

The proposal claims §4.2 is the corrected identity ("Phase 1 §4.1 sign was wrong; this supersedes it"). The proposal's own §15.1 item 1 lists sign convention as a known open weakness with property tests still to write. **These two statements contradict each other in the same document.** Pick one position.

### B-2 — §11 DS3 is not equivalent to §4.1 under §3 storage

**Independent computation:**

DS3 (formal): `w_t(u)[own] = depot_w(u, t) + InFlight_w(u, t)` with `InFlight = Σ_{τ : non-terminal} signed_qty(τ, w, u)`.

Rearranged: `depot = own − InFlight`.

§4.1 (algebraic, securities): `depot = own + Σ PSS_payable − Σ PSS_receivable − depot_out + depot_in`.

For consistency: `−InFlight = Σ PSS_payable − Σ PSS_receivable − depot_out + depot_in`, i.e., `InFlight = −Σ PSS_payable + Σ PSS_receivable + depot_out − depot_in`.

If "InFlight" is defined as "net incoming quantity to w" (positive sign for receivables), then for our buy at T:
- One open obligation: receive 100 XYZ.
- `signed_qty = +100` (we are the receiver).
- `InFlight = +100`.

Plug into rearranged DS3: `depot = own − InFlight = 100 − 100 = 0` ✓. Good, DS3 works.

But §4.1 with §3 storage gives `depot = 100 + 0 − (−100) = 200`. **§4.1 and DS3 produce different answers from the same state.** They cannot both be true. As shown in B-1, §4.1 needs its sign flipped; DS3 is correct as stated.

**Recommendation:** explicitly state, in §11 DS3, that `signed_qty` is positive for receive-direction; explicitly cross-reference the corrected §4.1; add a worked-example sub-block showing both formulae produce the same scalar on the §3 buy and on a sell. Until both representations agree on every example in the proposal, DS3 and §4.1 are not "two equivalent representations of one truth" — they are two formulae the proposal happens to display side by side.

### B-3 — Path-independence claim across full lifecycle including a fail is not demonstrated

§3.7 demonstrates path-independence for the SUCCESS lifecycle (T → T+1 → T+2 settled): cumulative PnL = sum of daily PnL = +150. ✓ I verified this independently:
- V_T = 1,000,000; V_{T+1} = 995,000 + 100×52 = 1,000,200; V_{T+2} = 995,000 + 100×51.50 = 1,000,150.
- Daily: +200, −50. Sum = +150. Cumulative: V_{T+2} − V_T = +150. ✓

§6.3 introduces fails. §9.2 details the daily CSDR penalty accrual ("Daily accrual emits a small cash transaction (failing party → suffering party) atomically with `o_pen.csdr_penalty_accrued` update").

**The proposal nowhere demonstrates path-independence for the FAIL lifecycle.** Worked check (XYZ stays at 51 from T+2 through T+5; trade fails at T+5; we are buyer, GS fails to deliver):

Forward (sum of daily PnL):
- T → T+1: +200 (mark up to 52)
- T+1 → T+2: −50 (mark down to 51.50)
- T+2 → T+3: −50 (mark to 51.00) + penalty inflow (we are the suffering party). 100 × 50 × 0.0001 = $0.50.
- T+3 → T+4: 0 + $0.50 penalty.
- T+4 → T+5: 0 + $0.50 penalty.
- Sum daily: +200 − 50 − 50 + 0.50 + 0.50 + 0.50 = +101.50.

Backward (V_{T+5} − V_T):
- own(USD) at T+5: 995,000 + 1.50 (penalty cash inflows over 3 days) = 995,001.50.
- own(XYZ): still +100 per DS7.
- V_{T+5} = 995,001.50 + 100 × 51 = 1,000,101.50.
- Cumulative: 1,000,101.50 − 1,000,000 = +101.50. ✓

These agree if and only if the daily penalty cash flow is recorded as a real `own(USD)` move on the right day. §9.2 says it is, but the worked example never shows this and the path-independence theorem (§3.7, P10) is asserted only against the success case. The proposal's strongest invariant (DS1 + path-independence) is unverified across the failure branch — which is the branch most likely to break it.

**Worse:** if the failing party is US (we owe cash but cash hasn't been wired), the proposal is silent on whether the penalty hits our `own(USD)` (debit) or stays in `L_15.Obligation` of kind `CSDR_PENALTY` until paid. §9.2 says "Ledger does not compute penalties autonomously" but also says daily accrual emits a cash transaction. Which is it — accrual lives in L_15 only, or accrual is a real cash move? The two readings produce different intraday `own(USD)` values, which break or hold path-independence depending on which is canonical.

**Recommendation:** add §3.8 "Path-independence under fail" with a four-day worked numeric example, both in the success-then-fail and fail-then-buy-in branches. Pin whether daily penalty accrual is (a) L_15-only with a single cash move at monthly cycle, or (b) daily real cash move. Verify cumulative PnL = sum of daily PnL by independent computation in both readings.

---

## Unmitigated Major (M-N)

### M-1 — Failed-settlement carrying cost has no forward/backward reconciliation

The proposal introduces three independent "carrying costs" of a failed trade: CSDR penalty (§9.2, daily basis-point accrual), CRR Art 379 settlement-risk RWA (§10.5, ramping risk weight), IFRS 9 ECL Stage 2 (§10.4, lifetime expected credit loss). These are computed by three different formulas with three different cadences and three different sources of truth.

**They should agree at first order on a portfolio basis.** Total economic cost of a failing trade ≈ counterparty-PD × LGD × notional + CSDR penalty + opportunity cost of locked capital. Each of the three measures is a different projection of the same underlying credit and operational exposure.

The proposal does NOT require these three to agree, does not provide a worked example showing them computed forward (sum of daily charges) vs backward (lifetime ECL), and does not state what to do when they disagree. A trader looking at the same failed trade through three lenses (P&L impact, regulatory capital, accounting provision) gets three different numbers and the framework provides no reconciliation.

This is the same disease the proposal cures for the SUCCESS lifecycle (DS1: no projection of the open-window state may differ from the settled-state projection, holding price constant). The disease persists in the FAIL lifecycle because the three measures are fundamentally different functionals — not just different storage of the same scalar.

**Recommendation:** add §10.12 "Failed-trade economic-cost reconciliation" stating the relationship explicitly. Acknowledge openly that CSDR penalty + Art 379 RWA + ECL provision are three projections that should not be summed (double-count), and provide a worked example with one fail showing the three numbers and stating which ones flow to PnL, which to regulatory capital, which to accounting provisions. Without this, the framework's three risk views silently triple-charge or under-charge.

### M-2 — `pending_in / pending_out` rejection rationale is correct but incomplete

§1 rejects pending_in/pending_out as PositionState fields. I agree (this was my Phase 1 dissent and I withdrew it accepting projections-only). The rationale stated ("derivable from PS/PSS wallet family by constant-time scan") is correct.

However, the §4.4 morning-recon report uses `inflight_out` and `inflight_in` in the algebraic identity and §2.3 wallet-class enum lists `virtual_inflight_out` and `virtual_inflight_in`. These are wire-level inflight (cash actually leaving / arriving the nostro), distinct from PS/PSS settlement-obligation contras. The proposal does not explicitly distinguish:

- PS_payable/receivable: settlement obligation (between trade-date economic recognition and CSD finality).
- inflight_out/inflight_in: wire-level transit (between Ledger emitting payment instruction and bank confirming debit).

These are two different open windows. A cash payment can be "PS_payable settled" (CSD batch confirmed DvP) and yet "inflight_out" (the actual SWIFT/Fedwire payment hasn't completed clearing). On the same trade. Simultaneously.

Without naming this distinction explicitly, a reader cannot tell whether the §4.1 formula's `inflight_out` overlaps with `PS_payable` (double-count risk) or follows it serially (correct). My reading is that they are sequentially disjoint — `PS_payable` clears at T+2 via CSD finality, `inflight_out` bridges from instruction-emit to bank-debit-confirm — but this is inferred, not stated.

**Recommendation:** §2.2 or §4.1 should add a one-paragraph "Two-window taxonomy" stating: window 1 (PS/PSS) is bounded by trade-execution (T) and CSD finality (T+ISD); window 2 (inflight_out/in) is bounded by Ledger-instruction-emit and bank-debit-confirm. Sequentially disjoint per cash leg per direction. No double-counting in the recon identity. Diagram or worked example showing both windows on the same buy.

### M-3 — §6.4 partial-settlement child-obligation lives only in L_15, not in wallet structure

§6.4 says partial settlement spawns a "child obligation for residual" in L_15. The Move pattern in §6.4 directly debits/credits the SAME PSS_receivable and PS_payable wallets used for the original obligation. So the wallet structure does NOT bifurcate: there is one PSS_receivable balance walking down from -100 to -40 to 0; the L_15 row spawns a child but there is no child wallet.

This is a defensible design choice but it is implicit. A reader could reasonably expect a child wallet `PSS_receivable[w_us, GS, XYZ, child_oblig_id]` because §2.2 keys wallets per obligation-relevant scope. The proposal's keying is `(w, cpty, ccy_or_ISIN)` — one wallet per counterparty-and-unit, regardless of how many obligations are open against it. Aggregation, not per-obligation rows.

This means: if there are TWO trades with GS on XYZ, and one has 100 shares and another 200 shares, the PSS_receivable wallet shows -300, and partial settlement of the first trade (60 of 100) walks the wallet from -300 to -240. There is no per-trade decomposition of the wallet balance — the per-trade detail lives only in L_15.

This is fine, but it breaks the "drill down to individual trade for break investigation" claim in §1 (the rejection of CSD-level aggregate). At the wallet level, GS+XYZ+w_us is already an aggregate; the per-trade resolution is in L_15, requiring a join.

**Recommendation:** §2.2 should explicitly state the keying granularity ("per `(real_wallet, counterparty_LEI, ccy_or_ISIN)`, NOT per-trade — per-trade detail lives in `L_15.Obligation` and is recovered by joining PS/PSS-touching `L_13` Moves to `L_15` rows on `tx_id`"). Then either: (a) reword §1's "drill down to individual trade" claim to say "drill down via L_15 join", or (b) widen the keying to include `obligation_id` and accept the per-trade wallet cardinality.

### M-4 — `own(XYZ) = +100, own(USD) = +995,000` immediately after T is FVTPL-correct but bookkeeping-inconsistent without Form B

§3.2 post-trade snapshot:
- `w_us.own(USD) = +995,000.00`

This says "w_us still holds 995,000 USD on its own balance" — but the cash hasn't actually left the bank yet (`nostro_external = 1,000,000`). The recon identity reconciles this via PS_payable = +5,000.

Operationally fine. But §10.2 Form A vs Form B journal entries make this consistent ONLY in Form B, where the credit goes to "Settlement payable to counterparty" (a balance-sheet line distinct from cash). In Form A, the credit goes to Cash — meaning the GL Cash balance shows 995,000 while the bank statement shows 1,000,000, requiring a recon at every reporting date.

§10.2 declares Form B preferred but does not declare Form A forbidden. A firm choosing Form A reads `w_us.own(USD)` as cash-at-bank — wrong, because PS_payable hasn't cleared. The recon identity corrects this only if the recon engine knows to look at PS_payable; a naive consumer of `own(USD)` reading it as bank balance is off by the open-PS_payable.

Phase 1 cargo-cult risk: "I am told `own(USD)` is the cash balance"; reader does not know it includes uncleared payables in the open window. **The proposal does not give `own(USD)` a sharp name.** Is it cash-at-bank? Cash-economic? Cash-trade-date? Per DS1 it is the trade-date economic balance, which differs from cash-at-bank by exactly `Σ PS_payable − Σ PS_receivable` over the open window.

**Recommendation:** in §2 introduce the term "trade-date cash balance" (or "economic cash balance") for `own(ccy)` and contrast it with "settled cash balance" (= nostro_external) and "cash-at-bank" (= nostro_external minus inflight). The three are distinct quantities and the proposal must name all three to satisfy the stranger test. Then §10.2 should state that Form A is forbidden in v11.0 (it conflates trade-date cash with settled cash) and only Form B is permitted at the GL primitive layer — Form A may exist as a derived view if any user genuinely needs it.

### M-5 — T+0 atomic discharge predicate creates a race the proposal does not address

§6.2 says T+0 collapses the open window to ε seconds. But §5.4 mandates: "no FSM transition without an attested envelope." For T+0 atomic on-chain, the attestation arrives at the same atomic-transaction boundary as the trade itself. So the FSM transition `EXECUTED → INSTRUCTED → SETTLED` happens in one atomic step.

But the FSM is defined as three discrete states with named transitions. If all three transitions are atomic, what is the observable state during the atomic boundary? Is `Pending` ever observable? Is `INSTRUCTED` ever observable? §6.2 hand-waves "vanishingly improbable" for FAILED but does not say what happens to the intermediate states.

This matters because: if a downstream consumer (risk system, regulatory reporter) polls `MoveStream[tx_id].settlement_status` between the trade-emit and the on-chain finality, what does it see? If `EXECUTED` for ε seconds, then poll-and-cache risk may serve stale state. If state-jumps are visible only at the boundary, then `EXECUTED` is unobservable in T+0 mode, breaking the assumption that all 7 status values are reachable in all variants.

**Recommendation:** §6.2 should pin the observability convention for T+0. Either: (a) intermediate states are observable for ε seconds (FSM transitions are sequential within the atomic boundary), or (b) only `SETTLED` is observable in T+0 mode (FSM degenerates to a single state). DS12 (variant degeneration) currently claims DS1–DS11 hold without modification — but observability of intermediate FSM states is implicit in DS5 (replay determinism) and DS8 (status monotonicity), and the proposal must say which states are reachable in each variant.

### M-6 — §7.9 SBL recon identity is sign-consistent with itself but not with §4.1

§7.9: `own_e(u) + borr_e(u) − onloan_e(u) − Σ_{i ∈ open(e,u)} signed_qty(i) = D(e, u)` where signed_qty is positive for receive, negative for deliver.

Apply to §3 buy: own = 100, borr = 0, onloan = 0, signed_qty = +100 (we are receiver). LHS = 100 + 0 − 0 − (+100) = 0. RHS = depot = 0 ✓.

Now apply §4.1 to same state (with corrected sign per B-1): depot = own + Σ PSS_payable + Σ PSS_receivable − depot_out + depot_in = 100 + 0 + (−100) − 0 + 0 = 0 ✓.

Both identities work — but they use OPPOSITE sign conventions on the receivable term. §7.9 has `signed_qty positive for receive`, contributing `−(+100) = −100` to LHS. §4.1 (corrected) has `Σ PSS_receivable storage-negative for receive`, contributing `+(−100) = −100` to RHS. Numerically equivalent, conventionally opposite.

This works by accident in the buy case. In a SELL case (we deliver), §7.9 says `signed_qty = −q` (negative for deliver). §4.1 corrected says `Σ PSS_payable = +q` (positive when we owe). Both produce the right numeric answer — but a code path that mixes the two conventions (e.g., uses §4.1 storage but calls it `signed_qty` in §7.9 vocabulary) flips the sign and the recon silently breaks.

**Recommendation:** §7.9 and §4.1 must use the SAME sign convention. Either: (a) both use storage-signed (negative-for-receive on the receivable storage), with the formulae written to match storage; or (b) both use semantic-signed (positive-for-receive in the formula, with explicit negation when reading from storage). The proposal currently uses (a) for §4.1 (after my B-1 fix) and (b) for §7.9. Pick one. PO-3 names this; the proposal has not closed it.

### M-7 — `failure_reason` closed sum (§12.1) is asserted but G1 is open

§12.1 introduces `failure_reason = DeadlineMissed | NoCover | CounterpartyDefault | CsdReject | LegInconsistent | Manual`. Closes formalis G1.

But §13.1 G1 says CSDs publish reasons as ISO 20022 status codes whose `Reason4Choice` is open-ended in some variants. PO-5 names the per-CSD mapping as still to be produced.

The closed sum in §12.1 forces the type system to commit to a finite enum. ISO 20022 `Reason4Choice` does not. So the framework's `failure_reason` MUST normalise — either by mapping every observed CSD code into one of the closed-sum cases (lossy if `Other` is the dumping ground), or by widening the closed sum every time a new CSD code appears (breaks the "closed" claim).

The proposal handles this via `CsdReject of Csd_reject_code.t` where `Csd_reject_code.t` is "closed sum, ISO 20022 normalised". But the normalisation is an open obligation (PO-5). Until PO-5 ships, `Csd_reject_code.t` is not closed in fact, only in type.

**Recommendation:** acknowledge in §12.1 that `Csd_reject_code.t` is closed-by-fiat, with documented per-CSD mapping (PO-5), and an `OTHER → ESCALATE_HUMAN` sink. Property test: every observed CSD reject code over a 12-month historical replay must map to a known case OR to `OTHER`. If `OTHER` count exceeds 1% of fails, the closed-sum claim is dead and the type must widen. State this discipline explicitly so future maintainers don't silently bury a tail of `OTHER` codes.

---

## Minor (m-N)

### m-1 — §3.5 `Move 1: from = w_GS_broker, to = PSS_receivable` direction is correct but reads backward

The finality contra-transaction at T+2 has `Move 1: from = w_GS_broker, to = PSS_receivable[w_us, GS, XYZ], qty = 100`. This drives PSS_receivable from −100 → 0 (because conservation: from = −100, to = +100, plus PSS already at −100 means new balance is 0; from-side w_GS_broker goes 0 → −100). Reads backward to a first-time reader — "GS sends to PSS_receivable" sounds like crediting a receivable, but in storage it is zeroing-out.

**Recommendation:** add a one-line annotation under each Move in §3.5: `(drains PSS_receivable from −100 to 0; w_GS_broker walks to −100, mirroring GS's net-out)`. Helps the stranger test.

### m-2 — §3.7 path-independence verification scopes only `w_us`, not the system

The PnL theorem in §3.7 computes `V_{T+1}(w_us)` and `V_{T+2}(w_us)`, on the real wallet only. Conservation (DS2) sums over real ∪ virtual wallets. If a downstream system computes "system PnL" by summing over all wallets it knows about, it must include the virtual ones — and PSS_receivable / PS_payable carry quantities that don't have a price function on them.

**Recommendation:** §3.7 should state explicitly that the PnL projection of interest is over real wallets only; virtual wallets carry quantities but no PnL contribution (their `own(u)` is a pure accounting shadow). Otherwise a careful reader concludes that summing over all wallets gives V = 0 always (by DS2), which is technically correct but useless.

### m-3 — §10.2 Form B journal entry uses "Settlement payable to counterparty" but this account does not appear in the wallet-registry enum (§2.3)

§2.3 wallet_class enum: `{real, virtual_cpty, virtual_PS_payable, virtual_PS_receivable, virtual_PSS_payable, virtual_PSS_receivable, virtual_nostro, virtual_depot, virtual_inflight_out, virtual_inflight_in}`.

§10.2 GL entry: `Cr Settlement payable to counterparty 5,000.00`.

The mapping from wallet `PS_payable[w_us, GS, USD]` to GL line "Settlement payable to counterparty" is implicit. A GL system needs a chart-of-accounts mapping. The framework owes the mapping table.

**Recommendation:** §10.2 should reference an explicit ledger-account mapping: each wallet_class corresponds to a specific GL line. Probably: `virtual_PS_payable → Settlement payable to counterparty`; `virtual_PS_receivable → Settlement receivable from counterparty`; etc. This is either §2.3 sidecar metadata or a separate §10.13 chart-of-accounts mapping. Without it, the audit chain (§10.3) is structurally broken at the GL projection step.

### m-4 — §13.1 G3 (corporate-action bitemporal predicate) is correctly framed but the worked example would help

PO-4 names the property test (2-for-1 split between obligation registration and deadline). The proposal says discharge predicates must be "bitemporal-state-functions, not snapshot values". Concrete: a predicate like `qty == 100` registered at T fails at T+2 if a 2-for-1 split occurred at T+1 making the correct delivery 200 shares. The property must read latest `with_corrections_through` knowledge time.

**Recommendation:** §6 (variants) should add §6.6 "Corporate action in window" with a worked numeric example: trade at T for 100 XYZ; 2-for-1 split at T+1; delivery at T+2 of 200 XYZ. Show predicate evaluation at T+2 fetches the post-split refdata and matches against 200, not 100. This is closing G3 / PO-4 with a concrete artifact.

### m-5 — DS2 (open-window conservation) sums over real ∪ virtual but does not include nostro/depot virtual wallets explicitly

DS2: `Σ_{w ∈ real ∪ virtual} w_t(u)[own] = 0`.

§2.3 lists `virtual_nostro` and `virtual_depot` in the wallet-class enum. Are these participants in the conservation sum? The §3 worked example shows `w_JPMC_nostro_USD.own(USD)` walking from 1,000,000 → 1,000,000 → 995,000 (changes only at T+2 finality, externally driven by camt.054).

If virtual_nostro is INCLUDED in DS2, then conservation is broken in the open window: at T post-trade, `Σ = w_us(995,000) + PS_payable(+5,000) + virtual_nostro(1,000,000) = 2,000,000`, not zero. The nostro is an external mirror, not a participant in our internal flows.

**Recommendation:** DS2 should explicitly EXCLUDE virtual_nostro and virtual_depot from the conservation sum. They are external-mirror wallets reflecting outside-the-system state, not internal wallets. Otherwise DS2 is structurally false in every open window.

### m-6 — §11 invariant table's "Type" column for DS3 says "runtime" but DS3 is also property-test (§13.2 PO-1)

DS3 is listed as runtime; PO-1 (the property obligation) says "show that PS_payable / PS_receivable wallets satisfy DS3 (recon identity) and DS6 (idempotency) under daily aggregation". Property-tested invariants are still runtime, agreed, but the proposal does not say what happens when the property test fails — does it block deployment, alert ops, or both? The DS labels invariants by mechanism but not by failure-mode policy.

**Recommendation:** add a column to the §11.4 invariant table: "Failure-detection cadence" (compile-time, deploy-time property test, runtime monitoring) and "Failure response" (block-deploy, page-ops, log-and-tolerate-with-tolerance). DS3 is deploy-time + runtime, with response = page-ops. DS17 is compile-time, response = build-failure.

---

## What works

1. **§1 convergence statement and rejection rationale.** The four rejected proposals (7th coordinate, u_circ unit, pending fields on PositionState, single-aggregate-per-CSD wallet) and their rationale are crisp. The 3-paragraph synthesis at the top of §1 is the best one-page summary of the framework I have read.

2. **§3 worked example.** PnL calculation is correct (verified independently both by direct valuation and by daily-decomposition); conservation tables are correct; transaction-block structure is implementation-faithful. This is the load-bearing artifact and it does its job — modulo the receivables-side sign issue (B-1) which is invisible in the buy case but corrupts the rest of the proposal.

3. **§5 lifecycle FSM.** Per-leg, not per-transaction, with the lattice projection. Witness-driven discharge (§5.4) and idempotency (§5.5) are correctly framed. The 3-state internal {Pending, Discharged, Compensated} + 7-state observable projection is the right factoring.

4. **§7 SBL composition (modulo M-6).** Orthogonality of GPM 6-tuple from settlement state, "no GPM coordinate moves at settlement" rule, and the worked short-sale-with-locate-then-borrow lifecycle (§7.3) are all sound. The "long that has never owned" framing in §7.7 is the right linguistic correction.

5. **§9.1 regulatory matrix.** Eight regimes with dedup keys, rule-set version pins, and DRR status. Bitemporal versioning discipline. This is operationally usable.

6. **§10.6 SOX/SOC1 control objectives.** Eight control objectives, three structurally separated roles, capability-typing as the system-property enforcement of segregation-of-duties. Converts a procedural assertion into a structural one.

7. **§11 invariants DS1, DS4, DS7, DS18.** These four are the framework's load-bearing structural commitments. They are stated correctly, with parents from v10.3, with severity. DS1 (economic-exposure-at-T) and DS18 (DvP atomicity at the type level) are the two most important and they are right.

8. **§12 type design.** `PairedObligation` (§12.2), phantom-typed wallet handles (§12.3), newtype dates (§12.4), trade-date / settle-date phantom basis (§12.6), Herstatt window in the type (§12.7). This is "what I cannot create I do not understand" applied to the type system: build the type so that the wrong code does not compile. §12.2's `PairedObligation` is the single highest-leverage commitment in the proposal — if implemented, half-settled DvP becomes structurally unrepresentable.

9. **§13 honest gaps.** G1–G12 are named, owners assigned, closing constraints stated. PO-1–PO-10 are the test-the-proposal-must-pass. This is correct discipline — name the open obligations, do not paper over them.

10. **§15.1 honest weakness list.** The Settlement Team identifies 8 known weaknesses and accepts them. Item 1 (sign convention on DS3) is the same weakness I am calling out as B-1 — the Settlement Team knows it is open, then claims in §4.2 to have fixed it. The fix is partial. The honest-weakness statement is correct; the §4.2 victory claim is premature.

---

## Stranger test: would a smart undergraduate emerge clear?

**Pass:** trade-date accounting and why it differs from settlement-date (§3 + DS1 + §10.1); the open-window state and why virtual wallets exist (§2.1 triple); DvP atomicity at trade time and at discharge time as different concerns (§12.2); the seven-state FSM and why it is per-leg not per-transaction (§5.2); CSDR penalty as a separate obligation in L_15, not a balance adjustment on `own` (§6.3 + §9.2).

**Fail:** the storage sign convention for receivables (must read three sections to infer); the difference between "PS_payable is cleared" and "wire is settled" (the two-window taxonomy from M-2); whether `own(USD)` is cash-at-bank or trade-date-economic-cash (M-4); whether DS2 conservation includes nostro/depot virtual wallets (m-5); what observable states exist in T+0 mode (M-5); how CSDR penalty, CRR Art 379 RWA, and IFRS 9 ECL relate to each other for the same fail (M-1).

A smart undergraduate could implement the success path correctly. They could not implement the fail path or the recon engine without re-deriving sign conventions from the worked examples. The proposal is one self-contained re-derivation away from the right shape; do that re-derivation and ship.

---

## Recommendation

**ACCEPT_WITH_CHANGES**, conditional on:

1. **B-1** fix the §4.1 sign on the receivables term (cash and securities), re-verify §4.2 with a sell example as well as a buy example, and reconcile this with §15.1 item 1 (state clearly: sign IS pinned, here is the test).
2. **B-2** restate DS3 in §11 with explicit `signed_qty` direction convention; provide one worked example showing §4.1 and DS3 produce the same numeric answer on the §3 buy and on a hypothetical sell.
3. **B-3** add §3.8 "Path-independence under fail" with a four-day worked example covering both fail-then-buy-in and successful-then-fail branches; pin whether daily CSDR penalty is L_15-only or real cash move.
4. **M-1, M-2, M-4** add the failed-trade carrying-cost reconciliation, the two-window taxonomy, and the trade-date-cash vs cash-at-bank distinction in the appropriate sections. These are clarity items, not rework.
5. **M-5** pin observability convention for T+0 / atomic.
6. **M-6** unify sign convention between §4.1 and §7.9.
7. **m-1 through m-6** are nice-to-haves; one editing pass.

The proposal is sound architecturally. The blocking items are sign-convention and self-consistency cleanups, not redesigns. Round 2 implementation can begin in parallel with these fixes — but B-1, B-2, B-3 must be discharged before any code consumes the recon identity, the path-independence theorem, or the DS3 invariant.

The §12 type design is the single most valuable commitment. If the §12 phantom typing ships and B-1/B-2/B-3 are closed, the framework eliminates a class of bugs that has cost the industry billions. The architecture is right. The proof artifacts need one more pass.

> *"The first principle is that you must not fool yourself — and you are the easiest person to fool."*

The Settlement Team has not fooled itself on the architecture; it has fooled itself on §4.2 by verifying only the easy half. Do the other half.

— feynman
