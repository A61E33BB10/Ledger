# Round 1 Adversarial Review — HALMOS
## Phase 3 / Round 1 / Reviewer: halmos (exposition rigor)
## Subject: proposal_v1.md (Settlement Team unified design)

---

## Verdict: **ACCEPT_WITH_CHANGES**

The proposal is genuinely substantive — the §3 worked example is the strongest single artifact in the corpus to date, the seven rejected alternatives in §1 are argued (not asserted), and the §11 invariant register has visible quantifier discipline absent from prior drafts.

But it fails the Halmos test on three counts: **(1) no notation table is established before symbols enter use**, so by §3 the reader has accumulated a dozen undefined or self-defined glyphs (`PS`, `PSS`, `w_PS`, `o_sec`, `u_sale`, `tau_sale`, `D_0`/`D_2`/`D_8`, `o_pen`, `D_max`, `Δ_CSDR`, `κ_buyin`, `κ`, `Lambda_n`, `F_terminal`); **(2) terminology drift between sections** — the same concept appears as `PS_payable`, `w_PS_payable`, `PS_payable[w, cpty, ccy]`, `virtual_PS_payable`, `PS payable`, and (in §10) `w_cpty_v`; **(3) §11 quantifier hygiene is partial** — DS1, DS2, DS5, DS11 have explicit ∀-binders; DS3, DS4, DS6, DS7, DS9, DS13–18 have implicit or partial ones, undermining the very totality claim the section is for.

A new engineer reading this in the order printed will *succeed* at §3 (the worked example carries them) and *fail* by §7.3 (the SBL composition uses `w_C`, `u_sale`, `tau_sale`, `tau_loan`, `tau_discharge`, `tau_collateral`, `u_loan`, `u_collateral`, `u_recall`, `u_buyin`, `loc_1`, `w_D_brkrvirt`, `avail`, `coll_post/recv`, `D_max` without the notation having been agreed). An auditor will succeed at §10 (journal entries are correct) and fail at §11 (the invariants do not literally state what holds; the parent cross-references substitute for argument). A risk manager reading §3 will know exactly what is true at T+1 — the strongest result. The same risk manager reading §7.4 will not be able to tell whether `u_recall.state` and `u_sale.lifecycle_stage` are the same field, the same kind of field, or different kinds.

The proposal is one disciplined revision pass — not a re-architecture — from being implementation-ready exposition. Specifically: insert a §0 Notation table before §1, freeze terminology, normalise quantifier prefixes in §11, and replace the Greek-prefix sub-script ad-hoc symbols (`κ`, `Λ`, `Δ_CSDR`, `F_terminal`) with named English referents or document them in §0.

---

## Blocking issues

### B1. No §0 Notation table.

The proposal opens at §1 with `MoveStream`, `L_15 Obligation`, `PS`, `PSS`, `w_PS`, `virtual_PS`, `coll_pledged/coll_received/financed`, `T_exec`, `transferStatus`, `EndToEndId`, `sese.025`, `camt.054` — *seven different namespaces colliding in a single thesis paragraph (§1 line 4)*. The reader cannot decide whether `PS` is a wallet, a wallet-class, a quantity, or a mnemonic for "pre-settlement" until §2.1, where the triple table introduces three different referents for each of `PS` and `PSS` in the same row. By the time §2.2 appears with `PS_payable[w, cpty, ccy]`, the symbol has had three lives.

A Halmos-compliant draft begins:

```
§0. Notation
  Sets:
    W_real, W_virtual, W = W_real ∪ W_virtual    -- wallets
    U                                            -- units (cash + securities)
    T_dom = { T+0, T+1, T+2, ... }               -- settlement domain
  Wallet families (all members of W_virtual):
    PS_payable[w, c, ccy]    -- "we, on real wallet w, owe counterparty c
                                in currency ccy"
    PS_receivable[w, c, ccy] -- ...
    PSS_payable[w, c, s]     -- "we owe c in security s"
    PSS_receivable[w, c, s]  -- ...
  Coordinates: own (the only one this spec writes)
  Obligations: L_15.Obligation, with state ∈ {Pending, Discharged,
              Compensated, Defaulted}; per-leg.
  Transaction-level status: lattice
              Settled > PartiallySettled > Failed > BoughtIn
              > Instructed > Executed > Cancelled
  Decimal types: D_0 (integer), D_2 (cash major), D_8 (price), ...
  Time: T = trade-execution; t_d = intended-settlement; t_d^- = morning of t_d
```

Until this is at the top, every section is fighting an undefined-symbol load.

### B2. The "PS / PSS / `w_PS` / virtual_PS" namespace is not consistent.

Concrete instances (all in §2):

| Form | Where used | Meaning intended |
|---|---|---|
| `PS` | §1 thesis ("Virtual PS/PSS wallet contras") | the wallet *class* |
| `PSS` | §1, same paragraph | securities counterpart of class |
| `w_PS` | §2.1 row 2 | a *specific* virtual wallet of that class |
| `virtual_PS_payable` | §2.3 wallet_class enum | the *class label* in the registry |
| `PS_payable[w_us, GS, USD]` | §3.2 onward | a specific wallet, indexed |
| `PS_payable` | §4.1 boxed identity (Σ over cpty) | a family summed over cpty |
| `Σ PS_payable` | §4.4 morning recon row | abbreviation of the family sum |
| `w_PS_payable` | nowhere — yet implied by `w_PS` | conjectural |

A reader cannot know whether `PS_payable[w_us, GS, USD]` and `w_PS` and `virtual_PS_payable` are three names for the same thing or three distinct things. Pick one, fix the rest; in particular drop `w_PS` (§2.1 row 2 — the only occurrence) and drop `w_PS_payable` from any subsequent draft. The form `PS_payable[w, c, ccy]` is the workhorse and is the right primary form.

### B3. §11 invariants — quantifier discipline is partial.

A run-through of all eighteen:

| Invariant | Quantifier prefix? | Comment |
|---|---|---|
| DS1 | ∀ explicit | Correct. |
| DS2 | ∀ explicit | Correct. |
| DS3 | ∀ implicit ("for every real wallet w, every unit u, every time t") in prose, but the box equation has no binder | Move binder *into* the box. |
| DS4 | ∀ implicit ("for every settlement obligation o") | Move into the symbolic statement. |
| DS5 | ∀ explicit | Correct. |
| DS6 | ∀ implicit | Move in. |
| DS7 | ∀ partly explicit (∀ w, ∀ u, but "every settlement obligation" is in prose) | Move in. |
| DS8 | ∀ implicit | Move in. |
| DS9 | ∀ implicit; ∃ in symbolic statement is correct | Add ∀ for o. |
| DS10 | ∀ implicit | Move in. |
| DS11 | enumerated, not quantified | Convert to ∀ partial-event . (...) |
| DS12 | ∀ over variant set, but variant set is implicit | List variants in scope; quantify ∀ v ∈ {T+0, T+1, T+2, T+5+}. |
| DS13 | ∀ explicit (correct) | OK. |
| DS14 | ∀ implicit | Move in. |
| DS15 | ∀ implicit | Move in. |
| DS16 | ∀ implicit | Move in. |
| DS17 | ∀ implicit | Move in. |
| DS18 | ∀ implicit | Move in. |

The pattern: in eight of eighteen the symbolic statement assumes its quantifier from the surrounding prose. This is exactly the form of error that defeats the §11 totality claim: a reviewer asking "for which o does DS4 hold?" cannot answer from the symbolic line alone. The Halmos rule (statements are sentences, not fragments) requires the binder be in the formula.

### B4. Greek and ad-hoc symbols introduced without a home.

Counted occurrences of symbols that are introduced parenthetically, in passing, or by reference to a section that does not define them:

- `Λ_8`, `Λ_13`, `Λ_14`, `Λ_15` — DS5, DS9, DS17, DS10. These are referenced as parents but the proposal never lists what each Λ is. The reader is asked to remember a numbered Greek catalogue from a different document.
- `κ_buyin(τ_buyin, o_buyin)` — DS9, sole occurrence. `κ` denotes "compensation handler" (inferable) but never glossed.
- `Δ_CSDR` — DS9, sole occurrence. Inferable as "CSDR cure window" but never defined.
- `F_terminal` — DS13, sole occurrence. Inferable as "terminal status set" but never enumerated.
- `D_max` — §6.4, §13 PO-9, sole non-table occurrences. Inferable as "max recursion depth of partial-fill cascade" but the value (jane_street: 2; sbl/temporal: recursive) is *the open question itself*.
- `tau_sale`, `tau_loan`, `tau_discharge`, `tau_collateral`, `tau_buyin` — §7.3, §7.8, §7.6 — Greek "τ" rendered as ASCII, used as transaction-name variable; would be cleaner as `τ` consistently, or as `tx_sale`/`tx_loan` etc. consistently. Pick one.
- `u_sale`, `u_loan`, `u_recall`, `u_buyin`, `u_collateral`, `o_sec`, `o_cash`, `o_pen` — §7, §10. `u_*` is used for both *units* (the StatesHome map) and *obligations* (here). The reader cannot tell §7.3 `u_sale.state Pending → Discharged` from a coordinate write on a unit. In v10.3 `u` is the unit; if obligations are now also `u_*`, the namespace has collapsed.

This is the single most repairable category. Pick: obligations are `o_*`. Transactions are `τ_*` (or `tx_*`). Units are `u`. Wallets are `w_*`. Then sweep §7 and §10.

### B5. `u_sale` vs `u_loan` vs `o_sec` — obligation naming is bimodal.

§7.3 uses `u_sale`, `u_loan`, `u_recall`, `u_buyin`, `u_collateral` for obligations. §10.2 uses `o_sec`, `o_cash`. §11 uses `o`, `o_pen`, `o_buyin`, `o_ccy1`, `o_ccy2`, `o_fx`, `o_rem`. **Three conventions for the same kind of object in three sections of the same document.** Pick one (`o_*`) and apply universally.

### B6. §3.2 — the canonical worked example references undefined `PSS_receivable[w_us, GS, XYZ]` *as a source of a Move*.

Line 176:
```
Move 1: from = PSS_receivable[w_us, GS, XYZ]
        to   = w_us
        unit = XYZ
        qty  = D_0(100)
```

The §2.2 wallet-keying paragraph says `PSS_receivable[w, cpty, ISIN] = "cpty owes w: securities arriving"` and then shows in §2.2 line 78 that `PSS_receivable` is the *receivable* — i.e., we are *owed* the securities. Move 1 then transfers FROM this receivable TO `w_us`. This is internally consistent (you are draining the claim into your own position), but the worked example does *not stop to explain* that draining a receivable wallet is the move primitive that makes the claim concrete. A reader at first encounter will read "Move 1 from PSS_receivable" as "I am giving up my receivable to acquire 100 shares" — and then the Move 2 line "from = w_us, to = PS_payable" reads as "I am giving up my own cash to incur a payable" — *both correct mental models for what is happening, but neither one matches the wallet-class doctrine in §2.2*.

The fix is one paragraph at the top of §3.2:

> *Move conventions on virtual wallets.* A `PSS_receivable` wallet, signed correctly per §2.6, holds the **negative** of the open-claim quantity: when we are owed 100 XYZ, `PSS_receivable[w_us, GS, XYZ].own(XYZ) = -100`. The trade-time move "from PSS_receivable to w_us" with qty = +100 is therefore the algebraic statement "`PSS_receivable.own(XYZ) -= 100; w_us.own(XYZ) += 100`," which leaves `PSS_receivable` at `-100` (we now have a receivable for 100). At finality the reverse move (from `w_GS_broker`, to `PSS_receivable`, qty = +100) brings `PSS_receivable` back to 0.

The reader who has this paragraph reads §3.2–§3.7 without any wallet-sign confusion. The reader who lacks it spends ten minutes on a sign-checking arithmetic loop on §3.6's tables (where the columns confirm the convention but only post-hoc). The §3.2 wallet snapshot at line 220–227 (which does show `PSS_receivable.own(XYZ) = -100` after Move 1) confirms the convention but does not state it as a rule.

### B7. §11 DS3 — the right-hand side embeds `InFlight_w(u, t)` which is *defined under the formula, not over it*.

```
$$w_t(u)[\text{own}] = \text{depot}_w^{\text{custodian}}(u, t) + \text{InFlight}_w(u, t)$$

with $\text{InFlight}_w(u, t) = \sum ...$
```

The parenthetical-`with`-clause is the dual of the boxed formula in §4.1, which is the same identity but with `Σ PS_payable` and `Σ PS_receivable` and `inflight_out`/`inflight_in` *named*. The two should match symbol for symbol. They do not: §4.1 has five terms on the RHS, DS3 has two. The reader cannot tell whether the §4.1 boxed identity is *the same theorem* as DS3 or a different one. (It is the same. Make this explicit.)

---

## Major issues

### M1. §3.6 conservation summary and §4.1 reconciliation identity disagree silently on what "Σ_internal" means.

§3.6 USD table column "Σ_internal" sums only the three internal wallets: `w_us`, `PS_payable`, `w_GS_broker`, *omitting* `w_JPMC_nostro_USD`. §4.1's identity *includes* nostro on the LHS (`nostro_external = ...`) which is the recon identity, not the conservation identity. The two are doing different jobs but use a confusingly similar shape. A reader following the spec front-to-back encounters §3.6 first and §4.1 second, and §4.1 reads as "an identity that, at first glance, contradicts §3.6's row." It does not — but the proposal does not say so.

Fix: at the top of §4, one paragraph stating "the recon identity (§4.1) is *not* the conservation identity (§3.6, DS2). Conservation is about the closed system of internal wallets including virtual nostro/depot mirrors. Recon is between the closed system and an external-attestor balance, and reduces to conservation only when no inflight contras are open."

### M2. §3.5 emits Move 1 with `from = w_GS_broker` *into* `PSS_receivable[w_us, GS, XYZ]`, which contradicts §2.2's keying rule.

```
Move 1: from = w_GS_broker
        to   = PSS_receivable[w_us, GS, XYZ]
        unit = XYZ
        qty  = D_0(100)
```

§2.2 says `PSS_receivable[w, cpty, ISIN]` is keyed by `(w, cpty, ISIN)`. So `PSS_receivable[w_us, GS, XYZ]` is "GS owes us 100 XYZ". The intent of the Move is "GS delivers 100 XYZ to drain the receivable". The arithmetic works out (`PSS_receivable.own(XYZ): -100 → 0`). But the *direction* of the Move ("from `w_GS_broker`, to `PSS_receivable`") inverts the intuitive flow — the receivable is being *credited* (drained toward zero), not *debited*. The reader who builds intuition from §2.2 will expect the move to read "from `PSS_receivable` to `w_us`" or "from `w_GS_broker` to `w_us`" — neither of which appears.

Recommendation: in §3.5, replace the move-block prose with the explicit balance-delta rule: "Move 1 ΔPSS_receivable = +100 (drains from −100 to 0); ΔGS_broker = −100. Move 2 ΔPS_payable = −5,000; ΔGS_broker = +5,000." Then the conservation table in §3.5 falls out by inspection. The current form requires the reader to mentally re-sign every move.

### M3. §5.2 says "per-leg, not per-transaction" but §3.2 emits two L_15 register lines under a single transaction `TX1`, while §3.5 issues a single `MoveStream[tx_id].settlement_status` update.

The architecture is consistent (per-leg L_15 row, transaction-level status as MAX projection), but a careful reader sees the §3.2 prose say "**Atomic** with the move pair: register obligations in L_15" — registering two obligations atomically with one transaction, then in §3.5 updating *both* obligations *plus* the transaction-level status atomically — and asks: "is the L_15 update atomic with the move pair or not?" The answer is yes, but §5.2 refines this only as "MAX projection" without restating the atomicity. Add: "**The L_15 obligation register is a sub-row of the transaction-level commit; both obligations and the transaction-level status row commit atomically with the move pair.**"

### M4. §6.4 partial settlement section uses `attempt_seq` in `tx_id` formula but §3.2 uses just `hash("ECON_REC", "BUY", ...)`.

§3.2:
```
tx_id = hash("ECON_REC", "BUY", "XYZ", 100, 50.0000_0000, GS_LEI,
             "2026-04-30T14:32:11Z")
```

§6.4:
```
TX_partial_2 (T+4):
  tx_id: hash("FINAL", TX1.tx_id, sese.025_partial2_msg, 1)
```

(the trailing `, 1` is the `attempt_seq`). §3.5 has `tx_id = hash("FINAL", TX1.tx_id, sese.025_msg_id, camt.054_msg_id)` — no `attempt_seq` explicit, presumably because there is only one finality message per leg. §6.4 says explicit `attempt_seq` is needed for partial-fill collision resistance. The general rule is not stated. State it: **"`tx_id` for SETTLEMENT_FINALITY transactions is `hash("FINAL", trade_tx_id, witness_msg_ids..., attempt_seq)` where `attempt_seq` ∈ {0, 1, 2, ...} is monotonic per (trade, leg). For non-partial finality, `attempt_seq = 0` is implicit."** Or, equivalently, *always* include `attempt_seq` and make it `0` for non-partial. Pick one and apply.

### M5. §7.3 SBL example signs are not consistent with §3.2 conventions.

§3.2 Move 1 for the buy: `from = PSS_receivable[w_us, GS, XYZ], to = w_us, qty = +100`.
§7.3.2 short sale: `Move(from=w_C, to=PSS_payable[w_C, D, NVDA], unit=NVDA, qty=500)`.

These are correct (§3.2 is a buy of XYZ; §7.3.2 is a short sale of NVDA), but the *forms* differ: in §3.2 the `PSS_receivable` is the *source* (with negative starting balance), in §7.3.2 the `PSS_payable` is the *destination* (with positive resulting balance). A reader who learned the convention from §3.2 will not be able to predict the §7.3.2 sign without re-deriving from "we owe D" semantics. Add a one-line rule in §2.2:

> **Direction of move on a virtual wallet — convention.** A *positive-balance* virtual wallet (e.g., PS_payable holds "we owe") is built up by moves *into* the wallet from `w_real`, and drained by moves *out of* the wallet at finality. A *negative-balance* virtual wallet (e.g., PSS_receivable holds "we are owed") is built up by moves *out of* the wallet to `w_real`, and drained by moves *into* the wallet at finality. (Balance interpretation: positive = liability; negative = asset; absolute value = open exposure.)

With this rule, §3.2 and §7.3.2 are both predictable on first read.

### M6. §11 DS1 statement is correct but its "equivalently" reformulation introduces a quantifier-free claim.

```
equivalently: there exists no projection Π over (move stream + status overlay
+ obligation log) whose value during [T, t_d^-] differs from its value after
τ has reached `Settled`, holding the price function constant.
```

This is the *contrapositive of an existential claim*, but lacking explicit ∀-bindings (over which projections? all? all "consumer-facing" projections? all projections satisfying property X?). The statement is also subtly different from the boxed equation above it — the boxed equation says "the own coordinate at t equals own at T plus signed deltas of moves of τ at T", which is actually a *strict* equality (deterministic). The "equivalently" formulation is *projection-invariance* (universal over projections), which is stronger. State which is the canonical form. (Recommendation: the boxed equation is the invariant; the projection-invariance is a corollary stated separately as DS1.cor.)

### M7. §13.1 G3 and G4 reference "ESMA grace per CSDR Art 7" and "DTC PvP-style → manual ops" without any forward to where these are codified.

A future contributor closing G3 needs to know whether ESMA-grace is to be encoded in `L_4 CalendarConvention`, `L_7^P PolicyConfiguration`, or `L_16 ReferenceMaster`. The proposal mentions all three layers in §6.1 but never specifies which layer owns CSDR grace windows. Without this, the gap-closing PO is under-specified. (Recommendation: state the home of every external parameter in a §0 table.)

### M8. The `lifecycle_stage` vs `state` vs `settlement_status` field-name trio is not normalised.

| Section | Field name | On what |
|---|---|---|
| §1 thesis | `MoveStream[tx_id].settlement_status` | transaction-level |
| §2.1 | `state` | L_15 obligation row |
| §2.4 | `MoveStream[tx_id].settlement_status` | transaction-level |
| §3.2 | `MoveStream[tx_id].settlement_status` | transaction-level |
| §5.1 | `Pending → Discharged` | per-leg state |
| §5.3 | both `state` (per-leg) and `settlement_status` (tx-level) | both |
| §6.4 | `L_13 status` | transaction-level (third name) |
| §7.3 | `lifecycle_stage` | obligation (fourth name) |
| §10.6 | `obligation.lifecycle_stage` | obligation (per CO-8) |
| §12.1 | `lifecycle_stage` | obligation |
| §15.2 | `lifecycle_stage` | obligation |

**Four names for two fields.** The proposal converges, but the naming is in active drift. Pin the names: per-leg is `obligation.state`; transaction-level is `tx.settlement_status`. Sweep all sections. (`lifecycle_stage` should disappear or be aliased.)

### M9. §8.1 CDM cross-walk table column headers are inconsistent across sub-tables.

Five sub-tables headed "Trade-time recognition (T) — economic side", "Open-window state (T < t < T+2)", "Settlement at T+2 success", "Settlement at T+2 fail/partial", "Composition layer". Each has columns "Ledger element | CDM 6.0.0 | Type / file". Within the rows, "CDM 6.0.0" is variously "Direct", "Direct (with conflation)", "Direct (terms)", "Direct (semantic-only)", "Partial", "Missing", "Missing — Gap N", and "Missing" with no Gap pin. Categorise once; apply uniformly. (Suggested closed sum: `{Direct, Direct (qualified), Partial, Missing (gap), Missing (out of scope)}`.)

### M10. §11 DS3's "InFlight_w(u, t)" sign convention is opposite of §4.1's box.

§4.1 box: `nostro_external = own + Σ PS_payable - Σ PS_receivable - inflight_out + inflight_in`.
§11 DS3: `own = depot_external + InFlight`, with `InFlight = Σ_τ signed-qty(τ, w, u)` over τ with status non-terminal.

If we equate the two (substituting `own ↦ own`, `nostro_external ↦ depot_external`, `inflight_out, inflight_in ↦ InFlight`), the §4.1 form has the *external balance on the LHS*, the DS3 form has it *on the RHS*. They are equivalent by transposition, but the signs of the terms — and therefore the rule the reader learns — differ. Pin the canonical form once. (Recommendation: §11's algebraic version is the spec; §4.1's verbal version is the *consequence* for cash-recon. Make this explicit. In particular: in §4.2 the sentence "**Phase 1 §4.1 sign was wrong; this supersedes it**" is itself confusing because *this proposal's* §4.1 may turn out to disagree with *this proposal's* §11.DS3 — the reader cannot tell.)

---

## Minor issues

### m1. §1 thesis paragraph (line 4) is one 142-word sentence with seven clauses.

It serves as the abstract but reads as a list of seven adopted positions glued by semicolons. Break into three sentences, each one position-statement.

### m2. §1 "what was rejected" sub-section uses six different formats for the rejection blocks.

Some begin "**The 7th coordinate** (sbl Phase 1, withdrawn)." Some begin "**First-class unit `u^circ`** (cartan, halmos, ...)." Some begin "**`pending_in` / `pending_out` as PositionState fields**". Pick one format (suggested: bold candidate, italic *(proponent, status)*, then prose).

### m3. §2.1 table column "Writer (C11 cap)" is the only place "C11" is mentioned in §2.

Define on first use or remove the parenthetical. (C11 is StatesHome capability discipline; the reader has it in context but the §2.1 cell is the first occurrence in this document.)

### m4. §2.6 says "v10.3 §2.5 + §2.4" — these refer to the v10.3 ledger spec, not this document.

Make explicit: "(v10.3 spec §2.5, §2.4)". Repeated for every "v10.3 §X" reference in the proposal — ~30 occurrences. The convention should be: external references prefixed with the document, e.g. `(v10.3 §2.5)` or `(StatesHome §2)`. Internal references bare (`§2.5`).

### m5. §3.1 setup uses `D_8`, `D_18`, `D_0`, `D_2` decimal types without §0 introduction.

Glossed in §4.6 table — but that table is six pages later. Move forward or pre-define in §0.

### m6. §3.7 PnL calculation is done in dollars without units on the intermediate steps.

```
V_{T+2} = 995,000.00 × 1.00 + 100 × 51.50
        = 995,000.00 + 5,150.00
        = 1,000,150.00
```

USD throughout, but `1.00` is the price of USD-in-USD (always 1) and `51.50` is the price of XYZ-in-USD. The unit-of-account convention is implicit. Add a single-line comment: "(All values in USD; `P(USD) = 1` by convention; `P(XYZ) = $51.50` per §3.1 mark.)"

### m7. §4.1 box has one TeX over-set with `\;` padding on both sides — render-fragile.

```
$$\boxed{\;
\text{nostro\_external}(w, \text{ccy}, t) = w_t.\text{own}(\text{ccy}) ...
\;}$$
```

Stylistic only. Drop `\;` padding; KaTeX/MathJax handles boxed content fine without it.

### m8. §4.4 morning-recon table is in monospaced ASCII alignment but the column labels use mixed-case English ("counterparty | ccy | bucket | ..."), inconsistent with the §4.1 mathematical box style.

Standardise on the markdown-table convention (used in §2.1, §2.5, §3.6, §6.2, §8.x, §10.4, §10.6, §10.7) for tables that have header rows.

### m9. §5.1 7-state diagram uses ASCII art with `─►` arrows but §5.3 transition table uses prose arrows `→`.

Pick one. (Markdown-renderable Unicode `→` works in both.)

### m10. §6.2 "T+0 / atomic DLT" subsection says "FX leg becomes atomic PvP via on-chain or CLS-on-chain bridge" — `CLS` is mentioned three times in the proposal (§6.2, §9.3, §10.11) without expansion.

Spell out on first use: `CLS` = Continuous Linked Settlement.

### m11. §7.3.2 line 763 has `w_C   own NVDA = -500    (covered short, locate present)` — three spaces between `w_C` and `own`.

§7.3.4 line 794 has `w_C   own NVDA = -500 + 500 = 0` — same spacing. §7.3.5 line 814+ uses `w_C`'s for possessive in prose. Stylistic only; consistent indentation in code blocks helps eye-tracking.

### m12. §7.7 SQL pseudo-query is the only SQL that does not use uppercase keywords — `SELECT ... FROM ... WHERE` are uppercase but `entity_id`, `unit_id`, `coordinate('own')` etc. mix conventions.

§4.3 SQL uses uppercase keywords. Pick one. Stylistic.

### m13. §8.6 "What CDM 6.0.0 features NOT to use" — tempting to include here `lifecycle_stage` (which §1 says must NOT be a string) but the proposal puts that in §12.

§8.6 is "anti-patterns from CDM"; §12 is "type discipline at the Ledger level". They are adjacent concerns; cross-link with one sentence: "(See §12.1 for the analogous string-vs-closed-sum rejection at the Ledger type level.)"

### m14. §9.1 regulatory matrix is the densest in the document — eight regimes × eight columns.

The fonts make this hard to read at any markdown rendering width. Consider a four-column compressed form (Regime | Trigger | Format | Pin) with the four secondary columns moved to a footnote or sidecar.

### m15. §10.2 journal entries use inline accounting indentation (`Dr ...` at column 1, `Cr ...` indented) — readable but not standard double-entry notation.

Stylistic.

### m16. §10.3 audit-evidence-chain table column "Linked by" is the most operationally important column but the column header is the smallest.

Consider promoting (move it earlier in the column order, e.g., between "Source" and "Framework artefact").

### m17. §11 DS9 uses `Δ_CSDR` (a duration) and DS14 uses `t > t_d` (an inequality). The former is a *constant*, the latter is a *predicate*; both are invariants over the same domain.

Make the two notations parallel: e.g., DS9 with `t_d + Δ_CSDR < t` predicate, DS14 with `t > t_d` predicate.

### m18. §12.1 OCaml block is the only block in the proposal in OCaml-syntax; §3, §5, §6, §7 use a Ledger-DSL pseudo-code; §4.3 and §7.7 use SQL.

Three notations for code is acceptable, but §12 should open with a one-line note: "Type signatures rendered in OCaml; no implementation commitment." Otherwise a reader sees `module PairedObligation : sig ... end` and asks "is the Ledger written in OCaml?" — it is not (the framework is language-agnostic).

### m19. §12.5 "14 malformed cases" is enumerated 1–14 with no closing paragraph stating the *closure property* (these 14 are exhaustive of the construction-time-detectable malformations).

Add: "The list is closed by definition of `Obligation.create`. Future malformation classes are detected post-construction by the FSM (DS8) or at discharge (DS4); the constructor is not the detection site for these."

### m20. §13.1 gap names (G1–G12) and §13.2 PO names (PO-1–PO-10) are not cross-referenced.

§13.2 PO-1 corresponds to §4.1 / DS3 / DS6; PO-2 to G9; PO-3 to DS3 sign; PO-4 to G3; PO-5 to G1; PO-6 to G11; PO-7 to §11 type-vs-runtime; PO-8 to §11 TLA+; PO-9 to DS11; PO-10 to §5.5. None of these mappings are stated. Add a "G ↔ PO" cross-reference column.

### m21. §14 "out of scope" — five items, each with one paragraph. Item 5 (mass cancellation) is the only one without a sentence on *who owns the future scope* (the other four name an owner: treasury, jane_street, "the legal layer", "v10.3 §13").

Add: "Mass cancellation owner: governance + jane_street operations runbook."

### m22. §15.1 "weaknesses" item 8 talks about migration cost being "real" but does not number the cost.

Item 8 says "~14 weeks per minsky §12". Confirm: 14 weeks at 1–2 engineers from §12.9. State it once with a number, not as a parenthetical. (Otherwise a reader who reads §15.1 first will not know whether the cost is one week or one year.)

### m23. §15.3 ends with "submission to Phase 3 Round 1 adversarial review" but the proposal *is* the submission. Either delete this clause or make it clear this is the cover note.

---

## What works (deliberately)

The §3 worked example is the strongest single artifact in the proposal. **Every wallet, every move, every conservation row is grounded in concrete numbers.** A reader who has read §3 and nothing else can sketch the deferred-settlement architecture on a whiteboard. Specifically:

1. **§3.5's "the position on `w_us` is invariant from T through T+2"** is the load-bearing claim of the entire spec, and the table at §3.6 *proves it row by row*. This is exposition at the level of v10.3 §13's SBL worked examples — possibly better.

2. **§1's seven rejection blocks** argue against alternatives, not assert against them. The 7th-coordinate rejection in particular ("Margaret Chen withdrew this in Phase 2 §0 after re-weighing three arguments") is the kind of authorship discipline that lets a future reader re-trace the design. The `u^circ` rejection lists eight named proponents and says explicitly "Matthias retains the dissent for the historical log; recommends revisit when CDM 7.0 ships an Obligation type" — exemplary.

3. **§5.4's "no fail by inference"** rule is one sentence, three preconditions, complete. The §6.4 partial-settlement worked example follows directly.

4. **§11's eighteen invariants** are the right granularity (not three; not fifty). The named-vs-numbered policy ("DS1 — Economic-Exposure-at-T") makes them quotable in subsequent discussion.

5. **§13.1's twelve gaps** are honest. G8 explicitly says "not closable by formal proof" — this is the right answer for a liveness gap under cluster outage; a less honest spec would assert closure with a hand-wave.

6. **§9.1 regulatory matrix** is the most complete cross-walk in the corpus. The "Dedup key" and "Rule-set pin" columns are the operationally critical ones and are populated for every regime.

7. **§6.2's "T+0 atomic DLT" degeneracy test** is the right framing: if T+2 → T+0 is a *parameter change* and not a re-architecture, the spec is generic. The §6.2 table makes the parameter-change concrete row by row.

8. **The §1.3 framing** ("the settlement window is a parameter, not an architecture") survives every section without contradiction. By §6.2, §9.3, §11.DS12 the reader trusts it.

---

## Recommendation

**ACCEPT_WITH_CHANGES.** The proposal is one disciplined revision pass from being implementation-ready exposition. Specifically, before Round 2:

1. **Insert §0 Notation table** addressing B1, B4, m3, m5.
2. **Normalise the four field-name drift** addressed in M8: `obligation.state` (per-leg), `tx.settlement_status` (transaction-level). Sweep all sections.
3. **Normalise obligation/transaction/wallet symbol forms** (B5): obligations are `o_*`, transactions are `tx_*` or `τ_*` (pick one), units are `u`, wallets are `w_*`.
4. **Move §11 quantifier prefixes inside the symbolic statements** (B3) — eight invariants currently have prose binders.
5. **Add the "wallet-sign convention" paragraph** (B6, M5) at the top of §3.2 and a one-line predictive rule in §2.2.
6. **Reconcile §4.1 box and §11 DS3 box** (M10, B7) — they are the same identity rendered with opposite sign conventions; pick one.
7. **Clarify the conservation-vs-recon distinction** (M1) at the top of §4.

These are all exposition fixes, not design changes. The architecture itself — virtual PS/PSS pairs + L_15 obligation row + transaction-level FSM as MAX projection over per-leg states + reconciliation as constant-time scan — is **converged and correct as far as I can verify.** §3 is the proof. §11 is the spec. §13.1 is the honest gap register. The proposal does pass the test "a reader who knows the existing corpus reads this and understands the deferred-settlement extension" — but the read is harder than it needs to be by perhaps a factor of two, due to the notational drift.

The Halmos test:

| Criterion | Result |
|---|---|
| Notation table exists? | **No** (B1) — required for ACCEPT |
| Define before use? | **Partial** — see B1, B4, m5 |
| Examples? | **Yes** — §3 is excellent |
| Structure apparent? | **Yes** — TOC at §1 line 6 is faithful |
| Read six times? | **Visible re-write evidence** (§4.2 explicit correction of own §4.1 sign; §15.1 honest weaknesses) |
| Implementable? | **Yes after fixes 1–7 above** |

The Settlement Team has done the hard work. What remains is the editorial pass.

— halmos
