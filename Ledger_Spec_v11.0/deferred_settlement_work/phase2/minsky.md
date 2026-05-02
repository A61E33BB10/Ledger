# Type Design — Make Illegal States Unrepresentable

**Author:** MINSKY (Phase 2, Settlement Team — type-design discipline)
**Scope:** the open settlement obligation between trade time `T` and settlement
time `T+k` for cash equities, generalised by parameterisation to `k ∈ {0, 1, 2, …}`
and to FOP / DvP / cross-currency / SBL-collateral variants.
**Position:** a definitive call between the Phase 1 minority (first-class typed
obligation unit `u_so` — Halmos, Cartan, Feynman, me) and the Phase 1 majority
(virtual wallets + `L_15` obligation row + transaction-level FSM — Jane Street,
Lattner, Karpathy, Ashworth, Temporal, Correctness, ISDA, Formalis, Geohot,
SBL, FinOps, Test-Committee, Matthias, Noether, Grothendieck).

This document is one section of a seven-author Phase 2 convergence. It owns
**type design**. It does not own move sequence, invariants, reconciliation,
CDM cross-walk, or worked examples beyond what is needed to make a
type-discipline argument.

---

## 1. Final Position — I adapt to the mainstream

After reading all 20 Phase 1 proposals, my Phase 1 design (first-class
`u_so` settlement-obligation unit) is **wrong on two counts**, and the
mainstream design (virtual wallets `w_cpty_v` + `L_15` obligation row +
transaction-level FSM `EXECUTED → INSTRUCTED → SETTLED | FAILED`) is right.

I withdraw `u_so`. I keep — and double down on — every type-discipline
weapon I proposed. The discipline migrates intact onto the mainstream
representation.

### 1.1 Why `u_so` is wrong

Two reasons. They are not subtle.

**(a) `u_so` violates StatesHome C12 (sector parsimony).** The StatesHome
3-map ruling is the canonical home for state in v11.0: `ProductTerms[u]`,
`UnitStatus[u]`, `PositionState[(w, u)]`. Three maps, no fourth `WalletState`
sector. Adding a new sub-universe `U_so ⊂ U` to carry obligation rows is
*technically* legal (it is a unit class, not a new map), but it forces every
consumer of `U` — pricing, valuation, conservation, regulatory projection,
PnL-explain, the test-generator universe — to deal with a new constructor.
The cost is paid by every reader, on every read site, forever.

The mainstream design pays the cost *once*, by promoting the existing
`L_15.Obligation` closed sum to a constructor `SettlementInstruction` already
named in v10.3 §13.2 Table line 3106 (Jane Street and Lattner caught this; I
missed it). Adding one constructor to a closed sum is a clean local change.
Adding a class of units is a global change. The first is library; the second
is language. Lattner is right. **Library wins.**

**(b) `u_so` is not load-bearing for the trade-date / settlement-date split.**
My Phase 1 used `u_so` to carry the lead–lag identity: `nostro = depot +
Σ live obligations`. Karpathy's proposal proves the same identity using the
counterparty virtual wallet's signed balance directly: `w_port(u) =
w_csd_v(u) + signed(w_cpty_v(u))`. The virtual wallet is **already** a
quantity in the wallet algebra; conservation is inherited; PnL is inherited;
time-travel is inherited. Promoting that quantity to a unit gains nothing
that the wallet balance does not give for free. It only renames the
counterparty's pending balance as a separate unit class.

The mainstream representation is therefore:

```
Trade at T:   (real wallet) ↔ (counterparty virtual wallet w_cpty_v)
              moves on (cash, security) units, conservation per unit, atomic.
              + L_15 row created atomically: SettlementInstruction obligation.
Settle T+2:   virtual-to-virtual rotation w_cpty_v → w_csd_v.
              + L_15 FSM: Pending → Instructed → Settled.
              No moves on real wallet. Position never updated by settlement.
```

This is what Jane Street, Karpathy, Lattner, Ashworth, ISDA, Temporal, and
Formalis converged on. The economic-exposure-at-T invariant (DS1) holds by
the move algebra of v10.3 §2 directly, not by any new unit. There is nothing
to add at the unit level.

### 1.2 What I keep

The type-design discipline does not depend on the choice of representation.
Every weapon I deployed against `u_so` works on the mainstream representation
at the same or lower cost. The remainder of this section is the discipline
applied to:

- the `L_15` obligation row,
- the transaction-level FSM,
- the virtual-wallet keys,
- the discharge entry-points,
- the date types and refinement types.

The thesis: **the mainstream design is correct; the type discipline is
non-negotiable; together they make the trade-date / settlement-date confusion
unrepresentable.** Without the type discipline, the mainstream design is one
typo away from a settlement-date PnL.

---

## 2. The Lifecycle FSM as a Sum Type

The transaction-level FSM `EXECUTED → INSTRUCTED → SETTLED | FAILED` (v10.3
§8.6) is *currently* a string in `cdm_payload.lifecycle_stage`. This is the
single most expensive design choice in v10.3 from a correctness standpoint.
A string admits typos (`"setled"` — Jane Street's example, shipped in
production at a Tier-1 firm), admits unknown values from upstream
deserialisation, and admits no exhaustiveness check at handler sites.

Replace with a closed sum, with carried evidence in each state, and a total
step function whose pattern match is checked exhaustive (warning-as-error).

### 2.1 The state type

```ocaml
(* Each state carries the evidence that justified the transition into it.
   A state without evidence is a type error: there is no way to construct
   [Settled] without an [sese.025] message id and a settlement timestamp. *)

type lifecycle =
  | Pending
      of { issued_at : Time.t
         ; tx_id     : Trade_id.t
         }
  | Instructed
      of { instructed_at : Time.t
         ; sese_023_id   : Iso20022_msg_id.t
         }
  | PartiallySettled
      of { qty_settled  : Qty.t            (* refined: 0 < qty_settled < qty_original *)
         ; partial_at   : Time.t
         ; sese_025_id  : Iso20022_msg_id.t
         ; remainder_id : Obligation_id.t  (* child obligation for the unsettled balance *)
         }
  | Settled
      of { settled_at   : Time.t
         ; sese_025_id  : Iso20022_msg_id.t
         }
  | Failed
      of { failed_at : Time.t
         ; reason    : failure_reason
         ; csdr_clock_started_at : Time.t option  (* Some iff CSDR-in-scope *)
         }
  | BoughtIn
      of { boughtin_at : Time.t
         ; buyin_ref   : Buyin_ref.t
         ; predecessor : Obligation_id.t   (* the original failed obligation *)
         }
  | Cancelled
      of { cancelled_at : Time.t
         ; correction_tx : Trade_id.t      (* the CORRECTION transaction id *)
         ; approver     : Operator_id.t
         }

and failure_reason =
  | DeadlineMissed
  | NoCover                              (* short obligation could not source inventory *)
  | CounterpartyDefault    of Lei.t
  | CsdReject              of Csd_reject_code.t   (* closed sum, ISO 20022 normalised *)
  | LegInconsistent        of which_leg            (* DvP partial, see Formalis G4 *)
  | Manual                 of Operator_id.t

and which_leg = SecurityLegOnly | CashLegOnly
```

**Three points worth pinning.**

- `failure_reason` is a closed sum, not a free string. Formalis names this as
  G1 (CSD failure-type closure). The type system forces the resolution: every
  ISO 20022 reason code is normalised to one of the constructors at ingest
  via a total mapping function; an `Other` constructor is the only legal
  fallback and it points to a manual-escalation handler. The closure is
  enforced by the test generator universe walking the variants.
- Each state's payload is **exactly the evidence the transition required**.
  `Settled` carries the `sese.025` id; `Cancelled` carries the
  `correction_tx`; `BoughtIn` carries the predecessor obligation id. There
  is no path to construct any state without its evidence.
- `PartiallySettled` carries a child-obligation id. The "obligation tree
  capped at depth 2" engineering rule (Jane Street) is enforced by a
  refinement on the *type* of `remainder_id`: `Obligation_id` of a
  partial-residual obligation is a distinct type, and its own `lifecycle`
  cannot itself be `PartiallySettled`. After two levels, escalate.

### 2.2 The total step function

```ocaml
type event =
  | Csd_instruct_ack    of { sese_023_id  : Iso20022_msg_id.t  }
  | Csd_settle          of { sese_025_id  : Iso20022_msg_id.t  }
  | Csd_partial         of { qty          : Qty.t
                           ; sese_025_id  : Iso20022_msg_id.t  }
  | Csd_fail            of { reason_code  : Csd_reject_code.t  }
  | Deadline_fired
  | Counterparty_default of { defaulter   : Lei.t              }
  | Buyin_executed      of { buyin_ref    : Buyin_ref.t        }
  | Cancellation_request of { correction_tx : Trade_id.t
                            ; approver    : Operator_id.t      }

(* The transition kernel.  Total over (state, event).  No wildcards.
   Compiled with -warn-error +partial-match: any unhandled (s, e) pair
   that is added later is a build break, not a runtime [assert false]. *)

type transition_result =
  | Step    of lifecycle           (* legal transition; new state                  *)
  | Reject  of reject_reason       (* illegal transition; documented refusal       *)
  | Idempotent                     (* same event arriving twice on terminal state  *)

and reject_reason =
  | Already_terminal  of lifecycle    (* Settled/BoughtIn/Cancelled cannot transition out  *)
  | Out_of_order      of { from : lifecycle; got : event }
  | Predicate_failed  of string       (* short-cover refinement violated, etc.    *)

let step (now : Time.t) (l : lifecycle) (e : event) : transition_result =
  match l, e with

  (* --- Pending ----------------------------------------------------- *)
  | Pending p,            Csd_instruct_ack a ->
      Step (Instructed { instructed_at = now; sese_023_id = a.sese_023_id })
  | Pending _,            Csd_partial pa ->
      let rem_id = Obligation_id.derive_residual ~parent:l in
      Step (PartiallySettled { qty_settled = pa.qty
                             ; partial_at = now
                             ; sese_025_id = pa.sese_025_id
                             ; remainder_id = rem_id })
  | Pending _,            Csd_settle s ->
      Step (Settled { settled_at = now; sese_025_id = s.sese_025_id })
        (* T+0 happy path: pre-instruction settlement, allowed *)
  | Pending _,            Deadline_fired ->
      Step (Failed { failed_at = now
                   ; reason = DeadlineMissed
                   ; csdr_clock_started_at = Some now })
  | Pending _,            Cancellation_request c ->
      Step (Cancelled { cancelled_at = now
                      ; correction_tx = c.correction_tx
                      ; approver = c.approver })
  | Pending _,            Csd_fail f ->
      Step (Failed { failed_at = now
                   ; reason = CsdReject f.reason_code
                   ; csdr_clock_started_at = Some now })
  | Pending _,            (Buyin_executed _ | Counterparty_default _) ->
      Reject (Out_of_order { from = l; got = e })

  (* --- Instructed -------------------------------------------------- *)
  | Instructed _,         Csd_settle s ->
      Step (Settled { settled_at = now; sese_025_id = s.sese_025_id })
  | Instructed _,         Csd_partial pa ->
      let rem_id = Obligation_id.derive_residual ~parent:l in
      Step (PartiallySettled { qty_settled = pa.qty
                             ; partial_at = now
                             ; sese_025_id = pa.sese_025_id
                             ; remainder_id = rem_id })
  | Instructed _,         Csd_fail f ->
      Step (Failed { failed_at = now
                   ; reason = CsdReject f.reason_code
                   ; csdr_clock_started_at = Some now })
  | Instructed _,         Deadline_fired ->
      Step (Failed { failed_at = now
                   ; reason = DeadlineMissed
                   ; csdr_clock_started_at = Some now })
  | Instructed _,         Cancellation_request c ->
      Step (Cancelled { cancelled_at = now
                      ; correction_tx = c.correction_tx
                      ; approver = c.approver })
  | Instructed _,         Csd_instruct_ack _ ->
      Idempotent
  | Instructed _,         (Buyin_executed _ | Counterparty_default _) ->
      Reject (Out_of_order { from = l; got = e })

  (* --- PartiallySettled -------------------------------------------- *)
  | PartiallySettled _,   Csd_settle s ->
      Step (Settled { settled_at = now; sese_025_id = s.sese_025_id })
  | PartiallySettled _,   Csd_fail f ->
      Step (Failed { failed_at = now
                   ; reason = CsdReject f.reason_code
                   ; csdr_clock_started_at = Some now })
  | PartiallySettled _,   Deadline_fired ->
      Step (Failed { failed_at = now
                   ; reason = DeadlineMissed
                   ; csdr_clock_started_at = Some now })
  | PartiallySettled _,   (Csd_instruct_ack _ | Csd_partial _
                          | Buyin_executed _ | Counterparty_default _
                          | Cancellation_request _) ->
      Reject (Out_of_order { from = l; got = e })

  (* --- Failed ------------------------------------------------------ *)
  | Failed _,             Csd_instruct_ack a ->
      Step (Instructed { instructed_at = now; sese_023_id = a.sese_023_id })
        (* re-instruction after fail; valid CSDR path *)
  | Failed _,             Buyin_executed b ->
      Step (BoughtIn { boughtin_at = now
                     ; buyin_ref = b.buyin_ref
                     ; predecessor = Obligation_id.of_lifecycle l })
  | Failed _,             Counterparty_default cd ->
      Step (Failed { failed_at = now
                   ; reason = CounterpartyDefault cd.defaulter
                   ; csdr_clock_started_at = (match l with
                                             | Failed f -> f.csdr_clock_started_at
                                             | _ -> None) })
  | Failed _,             Cancellation_request c ->
      Step (Cancelled { cancelled_at = now
                      ; correction_tx = c.correction_tx
                      ; approver = c.approver })
  | Failed _,             Csd_fail _ ->
      Idempotent
  | Failed _,             (Csd_settle _ | Csd_partial _ | Deadline_fired) ->
      Reject (Out_of_order { from = l; got = e })

  (* --- Terminal: Settled / BoughtIn / Cancelled -------------------- *)
  | (Settled _ | BoughtIn _ | Cancelled _),   _ ->
      Idempotent
        (* Late-arriving signals on terminal obligations are no-ops with
           the late-discharge race policy applied in the saga layer.
           See Correctness P-Late-Discharge-Race; this is the local
           idempotent leg. *)
```

The compiler enforces:

- every `(state, event)` pair is named;
- there are no wildcard patterns (`-warn-error +partial-match`);
- adding a new event constructor or a new state forces every existing
  match to be reconsidered explicitly.

This is the §3 of v10.3 P9 (Lifecycle Purity) made structural. The "no
silent drop" rule that Correctness names as P-Total-Handler is satisfied
by construction.

### 2.3 Why I killed wildcards

A wildcard arm `_, _ -> Idempotent` would compile, would pass tests, and
would silently absorb every novel event class that is added in 2027 when EU
moves to T+1 and a new substate appears. This is the path through which
Correctness's G-DS-3 ("AI-generated test asserts the implementation back to
itself") becomes a settlement loss. Every illegal pair must be named as a
`Reject` arm, with a `reject_reason`. **A `Reject` is exhaustively analysed
at the call site**; an exception is not.

This is the discipline that makes refactoring fearless. The cost is twenty
extra match arms that are mechanically derivable. The benefit is that adding
a new event class produces a build break in every handler that has not been
updated. Always cheaper than the production incident.

---

## 3. PairedObligation — DvP Atomicity at the Type Level

The DvP guarantee in v10.3 §8.4 states that the security leg and the cash
leg of a deliver-versus-payment trade discharge atomically: either both
commit or neither does. v10.3 currently expresses this as a transaction-
level atomicity (one transaction holds both moves; conservation per unit;
executor commits both or rolls back). That is correct at the trade time T.

It is **not enforced** at discharge time. The discharge transaction at T+2
runs in a different handler; nothing in v10.3 forbids that handler from
discharging the security leg without the cash leg, or vice versa. Formalis
names this as G4 (`LegInconsistent`). It is real: non-DvP CSDs report this
as a measurable fraction of failures, and even DTC has been observed (rare
but real) to report DvP success on one leg with a paired leg subsequently
restated.

The fix is structural: the discharge function consumes a single
`PairedObligation` value, not two independent obligations.

```ocaml
module PairedObligation : sig
  type t  (* abstract; constructed only via [pair] *)

  type pairing_error =
    | Different_trade_id  of Trade_id.t * Trade_id.t
    | Different_settle_dates  of SettleDate.t * SettleDate.t
    | Mirrored_qty_mismatch   of { sec_qty : Qty.t; cash_qty : Cash.t; expected_cash : Cash.t }
    | Same_side_pairing       (* both legs are deliver-side, or both receive-side *)
    | Wrong_leg_units         of { sec_unit : Unit_id.t; cash_unit : Unit_id.t }

  val pair :
       security_leg : Obligation.t   (* must be a security-leg obligation *)
    -> cash_leg     : Obligation.t   (* must be a cash-leg obligation *)
    -> (t, pairing_error) Result.t

  val security_leg : t -> Obligation.t
  val cash_leg     : t -> Obligation.t

  (* Both projections are total; no None case.  A [t] that is missing a
     side is unrepresentable. *)
end

(* Discharge consumes a [PairedObligation] atomically.  There is NO public
   function with type [Obligation.t -> ... -> DischargeResult.t].  Partial
   discharge does not type-check. *)

val discharge :
     PairedObligation.t
  -> csd_confirmation : Sese_025_msg.t
  -> now              : Time.t
  -> (DischargeResult.t, discharge_error) Result.t

and DischargeResult.t = {
    settled_security_leg : Obligation.t  (* now in [Settled _] *)
    settled_cash_leg     : Obligation.t  (* now in [Settled _] *)
    moves_emitted        : Move.t list   (* virtual-to-virtual rotations *)
  }

and discharge_error =
  | Already_settled    of Obligation_id.t
  | Confirmation_only_one_leg  of which_leg  (* the LegInconsistent case *)
  | Confirmation_quantity_mismatch  of { expected : Qty.t; got : Qty.t }
  | Csd_dvp_violation                (* CSD reports DvP succeeded but legs misaligned *)
```

The crucial point is **what is missing from the API**: there is no way to
build a single-leg discharge transaction from outside the module. The cash-
leg-only and security-leg-only failure paths route through `Confirmation_
only_one_leg`, which produces neither a `Settled` cash nor a `Settled`
security — both legs remain in `Instructed` (or transition to `Failed
LegInconsistent` per the κ_settle dispatch). Operationally: if the CSD says
"DvP success on cash, DvP fail on security", `discharge` returns
`Error (Confirmation_only_one_leg CashLegOnly)` and **neither balance
moves**. The break workflow opens. No partial PnL. No half-settled trade.

The discharge `pair` constructor validates at construction time: trade
ids must match, settle dates must match, qty × price = cash within
rounding tolerance (a refinement type — see §6 below). Pairing errors are
detected at trade time, before the obligation is ever submitted to the CSD.

### 3.1 Cross-currency: paired but per-leg

Cross-currency is a different shape — see §9 below. Briefly: a USD/JPY
trade produces **two** `PairedObligation`s, one per currency, with
different `SettleDate`s, and the asymmetry is exposed in the type. There
is no `CrossCurrencyPairedObligation` that promises atomicity across
currencies; the framework refuses to falsely promise what no CSD delivers.

---

## 4. Phantom-Tagged Unit Families — `exposure_bearing` vs `custody_bearing`

In Phase 1 I proposed phantom-tagging the *units* themselves
(`exposure_bearing` vs `custody_bearing` as type parameters on `Unit_id`).
That was overkill: it forced every consumer of `Unit_id` (pricing,
valuation, conservation) to carry the phantom parameter, and it duplicated
the work of the wallet-class distinction (real vs virtual).

The mainstream design already has the distinction at the *wallet* level:
`real wallet` (carries the buyer's economic position) versus `virtual
wallet` (carries the counterparty / CSD obligation). What was not in
v10.3, and what the type discipline must add, is a phantom tag on the
**wallet handle** — not the unit.

```ocaml
type real_wallet
type cpty_virtual_wallet      (* mirrors a counterparty's pending position *)
type csd_virtual_wallet       (* mirrors a CSD / nostro / depot           *)
type wallet_class =
  [ `Real of real_wallet
  | `CptyVirtual of cpty_virtual_wallet
  | `CsdVirtual of csd_virtual_wallet
  ]

(* A wallet handle carries its class as a phantom.  [w : real_wallet wallet_handle]
   versus [w : csd_virtual_wallet wallet_handle].  The same wallet can never be
   simultaneously real and virtual; the type system enforces this. *)
type 'class_tag wallet_handle = private {
    id      : Wallet_id.t
  ; class_  : wallet_class           (* dynamic shadow, used only for diagnostics *)
  }

val of_real    : Wallet_id.t -> real_wallet wallet_handle
val of_cpty    : Wallet_id.t -> cpty_virtual_wallet wallet_handle
val of_csd     : Wallet_id.t -> csd_virtual_wallet wallet_handle
```

The phantom-typed entry points then enforce **DS1 — economic exposure at
T — by construction**:

```ocaml
(* The trade-time emitter is the ONLY function that writes a real wallet.
   It is parameterised over the real wallet handle and a counterparty
   virtual wallet handle.  The CSD virtual wallet does NOT appear in the
   trade-time signature. *)

val emit_trade :
     real_wallet      wallet_handle    (* buyer's real wallet            *)
  -> cpty_virtual_wallet wallet_handle (* counterparty mirror            *)
  -> security : (Isin.t * Qty.t)
  -> cash     : (Currency.t * Cash.t)
  -> trade_date : TradeDate.t
  -> settle_convention : SettleConvention.t
  -> (Transaction.t * PairedObligation.t, trade_error) Result.t

(* The settlement-time emitter is the ONLY function that writes a CSD
   virtual wallet.  It does NOT take a real wallet handle.  A handler
   that tries to reach the real wallet from inside the discharge path
   does not type-check. *)

val emit_discharge :
     PairedObligation.t
  -> cpty_virtual_wallet wallet_handle  (* the SAME cpty handle from the trade *)
  -> csd_virtual_wallet  wallet_handle  (* depot / nostro mirror              *)
  -> csd_confirmation : Sese_025_msg.t
  -> (Transaction.t, discharge_error) Result.t

(* The conservation-checking executor accepts a transaction over any
   wallet class; it does not need to know which class a wallet has,
   because conservation is per-unit, not per-class.  But it cannot
   construct a wallet handle of any class — only the public constructors
   above can. *)
```

**This is what enforces DS1.** `emit_discharge` cannot be passed a
`real_wallet wallet_handle` because its signature accepts only
`cpty_virtual_wallet` and `csd_virtual_wallet`. A handler that tries to
write the buyer's `own[XYZ]` from the settlement-confirmation path is
ill-typed. Settlement-status mutation that touches `own` is structurally
unrepresentable.

This is the Jane Street I-1 invariant ("settlement-status transitions
write to obligations, never to positions") implemented at the type level.
Capability-tagged mutation (StatesHome C11) was already specified at the
*field* level; we lift it to the *wallet* level.

### 4.1 Where this discipline pays its rent

| illegal state | how this rules it out |
|---|---|
| Discharge handler debits the buyer's real wallet at T+2 | `emit_discharge` does not accept a `real_wallet wallet_handle`. Type error. |
| Trade handler accidentally credits the CSD nostro at T | `emit_trade` does not accept a `csd_virtual_wallet wallet_handle`. Type error. |
| Reconciliation projection sums real and virtual wallets together | `ledger_position` accepts `real_wallet`; `depot_position` accepts `csd_virtual_wallet`; their types are different; the sum is rejected by the type system unless an explicit projection is used. |
| Status-flag handler writes a real-wallet move | the move emitter is parameterised over its source/destination class; the only handler with the right class for a real wallet is `emit_trade` and `emit_correction`. |
| Migration of a status-FSM transition into a position move | the FSM's `Step` constructor returns a `lifecycle`, never a `Move.t`. The two are different types. |

Five entire categories of bugs eliminated, at the cost of three phantom
parameters.

---

## 5. Newtype Dates

```ocaml
(* Distinct date types.  None are interchangeable.  Each is constructed
   only through its smart constructor.  No public Date.t -> t cast. *)

module TradeDate : sig
  type t
  val of_clock : ClockAuthority.t -> Time.t -> t
  val to_date  : t -> Date.t                                 (* read-only export *)
end

module SettleDate : sig
  type t
  val of_trade_date :
       TradeDate.t
    -> SettleConvention.t      (* T+1, T+2, custom *)
    -> CalendarPin.t           (* L_4-pinned business calendar at trade time *)
    -> (t, settle_error) Result.t
  val to_date : t -> Date.t

  (* There is no public [of_date : Date.t -> t].  A SettleDate is always
     derived from a TradeDate plus a versioned convention.  This rules out
     hand-typed settle dates, which are the source of the v10.3 §8 latent
     bug class where [tx.timestamp] and [cdm_payload.settlement_date] drift. *)
end

module ValueDate : sig
  type t
  val of_settle : SettleDate.t -> t
  (* For cash equities, value date = settle date.  For repo, value date can
     differ; module exposes both constructors then. *)
end

module RecordDate : sig
  type t  (* the corp-action snapshot date; opaque, not used for settlement timing *)
end
```

The `SettleDate` constructor takes a `CalendarPin.t` as a third argument.
The `CalendarPin` is the bitemporal-pinned `L_4` calendar at trade time; it
makes the settle-date computation deterministic across replay and across
late calendar restatements. Formalis G7 (the "true at T+2⁻" semantics) is
addressed structurally: a `SettleDate` carries the calendar version it was
derived from. Replay produces the same `SettleDate` because it produces the
same calendar pin.

A handler that wants to settle "tomorrow" cannot pass a raw `Date.t` —
the type system rejects it. A handler that wants to compare a `TradeDate`
against a `SettleDate` cannot use `=` directly; it must lift both to
`Date.t` via `to_date` (which makes the lift visible, not invisible).
Confusion between `T` and `T+2` is a type error.

---

## 6. Smart Constructor `Obligation.create`

Every obligation reaches the `Pending` state through one constructor.
The constructor rejects every malformed obligation that the system can
detect at construction time.

```ocaml
type creation_error =
  | Non_positive_qty
  | Non_positive_cash
  | FoP_with_cash                          (* free-of-payment leg has nonzero cash *)
  | CashOnly_with_qty                      (* cash-only payment has nonzero qty   *)
  | Cash_qty_mismatch of { expected : Cash.t; got : Cash.t }   (* qty * price != cash, beyond rounding tolerance *)
  | Settle_date_in_past
  | Settle_date_not_business_day  of CalendarPin.t
  | Settle_date_before_trade_date
  | Same_party_both_sides   (* deliverer = receiver: nonsensical for DvP *)
  | Unknown_isin           of Isin.t       (* ISIN not in InstrumentMaster pin   *)
  | Unknown_currency       of Currency.t
  | Unknown_csd_mic        of Mic.t
  | Unknown_party_lei      of Lei.t
  | Cdsr_clock_misconfigured   (* CSDR-in-scope obligation lacks penalty config  *)

module Obligation : sig
  type t

  val create :
       trade_id          : Trade_id.t
    -> trade_date        : TradeDate.t
    -> settle_convention : SettleConvention.t
    -> calendar_pin      : CalendarPin.t
    -> deliverer         : Lei.t
    -> receiver          : Lei.t
    -> isin              : Isin.t
    -> qty               : Qty.t                 (* refinement: > 0 *)
    -> cash_currency     : Currency.t
    -> cash_amount       : Cash.t                (* refinement: > 0 except FoP *)
    -> price             : Price.t               (* refinement: > 0 *)
    -> csd_mic           : Mic.t
    -> dvp_kind          : [ `DvP | `FoP | `CashOnly ]
    -> cdsr_in_scope     : bool
    -> instrument_master_pin : InstrumentMasterPin.t
    -> party_master_pin  : PartyMasterPin.t
    -> (t, creation_error) Result.t

  val terms     : t -> obligation_terms
  val lifecycle : t -> lifecycle
  val id        : t -> Obligation_id.t
end
```

**Every malformed case rejected at construction:**

1. `qty ≤ 0` → `Non_positive_qty`.
2. `cash_amount ≤ 0` for DvP/CashOnly → `Non_positive_cash`.
3. `dvp_kind = FoP ∧ cash_amount ≠ 0` → `FoP_with_cash`.
4. `dvp_kind = CashOnly ∧ qty ≠ 0` → `CashOnly_with_qty`.
5. `|qty × price − cash_amount| > rounding_tolerance(currency)` →
   `Cash_qty_mismatch`.
6. `settle_date(trade_date, conv) < now()` → `Settle_date_in_past`.
7. `settle_date(trade_date, conv)` falls on a non-business day per the
   pinned calendar → `Settle_date_not_business_day`.
8. `settle_date < trade_date` → `Settle_date_before_trade_date`.
9. `deliverer = receiver` → `Same_party_both_sides`.
10. `isin ∉ instrument_master_pin` → `Unknown_isin`.
11. `cash_currency ∉ currency_master` → `Unknown_currency`.
12. `csd_mic ∉ csd_master` → `Unknown_csd_mic`.
13. `deliverer ∉ party_master_pin ∨ receiver ∉ party_master_pin` →
    `Unknown_party_lei`.
14. `cdsr_in_scope = true ∧ csd_master.csdr_regime(csd_mic) = None` →
    `Cdsr_clock_misconfigured`.

The smart constructor takes `instrument_master_pin` and `party_master_pin`
as explicit arguments rather than reading from a global registry. This is
what makes the constructor *reproducible* under replay (Correctness P-Idem-
Trade and Λ8): the same inputs produce the same `Obligation.t`, regardless
of the wall-clock time of the construction.

The constructor returns `Result.t`, never raises. Every error is an
explicit constructor in `creation_error`, which is itself a closed sum. A
caller that wants to be exhaustive over the error cases is forced by the
compiler to handle all 14 explicitly or to use a catch-all that is named at
its call site (and reviewable as such).

### 6.1 What I deliberately do NOT validate at construction

- **Conservation** (DS2). The smart constructor for an obligation is per-
  obligation; conservation is per-unit-per-transaction. The conservation
  proof obligation belongs at the executor (v10.3 §2.4), not here.
- **Counterparty creditworthiness** (ECL, Stage 1/2/3 migration). This is
  a runtime ECL computation (Ashworth DS-5), not a type-level fact. The
  obligation can be created against a counterparty in any credit state;
  the ECL accrual is downstream.
- **CSDR penalty rate**. The penalty rate table is versioned reference
  data; the obligation just stores `cdsr_in_scope`. The rate lookup at
  fail time uses `VersionPinSidecar`.
- **Inventory availability for short obligations**. A short-side
  obligation can be *created* without `avail ≥ qty`; the precondition is
  enforced at *discharge* time, not at obligation creation, because the
  short can be covered between trade and settlement (SBL borrow, recall).
  See §10 below.

Validation is *layered*. The type system catches everything that is local
to the obligation. Cross-event invariants are runtime per-event-class
proofs (StatesHome C2). The boundary is named, not negotiated.

---

## 7. Total Functions Over the FSM

Already covered in §2: the `step` function is total, returns a closed sum
`transition_result`, and pattern-matches exhaustively. The two non-trivial
cases:

**(a) Idempotency on terminal states.** `Settled`, `BoughtIn`, `Cancelled`
absorb every event as `Idempotent`. This is the late-discharge-race local
leg (Correctness P-Late-Discharge-Race): a `sese.025` arriving 100ms after
buy-in does not re-open the obligation. The saga compensation tower
decides whether the late discharge is queued-and-reconciled or canceled,
but the FSM's job is to refuse to transition out of a terminal state. The
type system enforces this by making `lifecycle` a closed sum and the
terminal-arm catch-all explicit.

**(b) Out-of-order rejects rather than crashing.** `Pending → Buyin_executed`
returns `Reject (Out_of_order ...)` rather than raising or silently no-
opping. The handler at the call site receives a `transition_result`, must
pattern-match, and must decide what to do with a `Reject`. The decision is
*always* the same in practice — log to `BreakRegister` (`L_18`) and route
to ops — but it is the *handler's* decision, not the FSM's.

This is the difference between a partial function and a total function with
an explicit failure encoding. The first crashes the workflow; the second
escalates with full context.

---

## 8. Phantom Types for Accounting Policy

Ashworth's ruling: trade-date accounting is the framework default. Settle-
ment-date accounting is permitted only as a downstream **projection**, not
as a primary state.

The type system encodes this:

```ocaml
type trade_date_basis    (* the framework's primary basis *)
type settle_date_basis   (* available only as a projection *)

(* The PnL function is parameterised by accounting basis. *)
type 'basis projection

val pnl_trade_date :
     wallet : real_wallet wallet_handle
  -> as_of  : Time.t
  -> trade_date_basis projection -> Money.t

(* The settlement-date projection requires an explicit policy attestation;
   it cannot be invoked silently from a generic context. *)

val pnl_settle_date :
     wallet : real_wallet wallet_handle
  -> as_of  : Time.t
  -> policy_attestation : SettleDateAccountingPolicy.t   (* required *)
  -> settle_date_basis projection -> Money.t

(* The two projections live in different types.  A function that returns
   [_ projection] without a phantom annotation does not type-check.
   A consumer that wants the trade-date answer reads [trade_date_basis
   projection]; one that explicitly wants the settlement-date view (e.g.
   for a held-to-collect IFRS sub-ledger) imports [settle_date_basis
   projection] with the policy attestation. *)
```

This is the discipline that protects the framework from a regression in
which a downstream consumer (margin, risk, MiFIR reporting) silently picks
up the settlement-date answer because some helpful refactoring exposed it
under the same name. The two are different types. A confusing call is a
type error.

The settlement-date projection is *not* the primary basis; it is a derived
view, available only with policy attestation. Migrating between bases
requires changing the type; it cannot happen by accident.

---

## 9. Cross-Currency Herstatt Visibility

For an FX-funded equity trade — say USD-funded purchase of a JPY-denominated
security — the framework produces **two `PairedObligation`s**, one per
currency, with **different `SettleDate`s** computed against different
calendars and different CSDs.

```ocaml
val emit_fx_funded_trade :
     real_wallet      wallet_handle
  -> cpty_virtual_wallet wallet_handle
  -> security : (Isin.t * Qty.t)
  -> cash_paid    : (Currency.t * Cash.t)   (* e.g. USD payment *)
  -> cash_received : (Currency.t * Cash.t)  (* e.g. JPY proceeds, but FX rebooks: actually the trade is "FX swap +
                                              * equity buy"; this is two paired obligations *)
  -> ...
  -> ( Transaction.t
     * PairedObligation.t   (* leg 1: equity DvP, e.g. JPY cash for JPY-listed shares *)
     * PairedObligation.t   (* leg 2: FX, e.g. USD for JPY *)
     , trade_error
     ) Result.t
```

The function returns a *tuple* `(equity_leg, fx_leg)`, not a synthetic
unified object. A consumer that wants to discharge "the FX trade" cannot;
there is no `discharge_fx : Transaction.t -> ...` because there is no type
that represents "the FX trade as one settlement object". The handler must
deal with the two legs explicitly.

```ocaml
val discharge_fx_trade :
     equity_leg : PairedObligation.t
  -> fx_leg     : PairedObligation.t
  -> equity_csd_confirmation : Sese_025_msg.t option   (* Some when CSD confirms equity leg *)
  -> fx_csd_confirmation     : Sese_025_msg.t option   (* Some when CSD confirms FX leg *)
  -> now : Time.t
  -> ( fx_discharge_state
     , discharge_error
     ) Result.t

and fx_discharge_state =
  | Both_pending
  | Equity_settled_fx_pending     (* Herstatt window: leg 1 done, leg 2 outstanding *)
  | Fx_settled_equity_pending     (* Herstatt window: leg 2 done, leg 1 outstanding *)
  | Both_settled
  | Asymmetric_fail of which_leg  (* one leg failed, requires Tier-2 saga escalation *)
```

The Herstatt window is **named** in the type. `Equity_settled_fx_pending`
and `Fx_settled_equity_pending` are explicit constructors of
`fx_discharge_state`; a handler that wants to "process the FX trade
settlement" cannot avoid pattern-matching on these states. The risk is not
eliminated — no ledger design can eliminate clock-skew across CSDs in
different time zones — but it is *unrepresentable to ignore*.

Compare to the alternative (a single `FxObligation` with one
`SettleDate = max(equity_settle, fx_settle)`): this collapses the two
clocks, hides the asymmetric window, and makes the Herstatt failure mode
look like a partial settlement of one obligation. The asymmetric type is
strictly more expressive.

This is the type-discipline analogue of Halmos's `(σ_S, σ_C)` pair, Cartan's
two-σ representation, and Formalis's parent-with-children obligation. They
are right that the FX trade is two obligations. The phantom-typed product
type makes that structural.

---

## 10. Where Type-Encoding Is Too Clever — Honest Boundaries

Six places where the type system stops and runtime validation takes over.

| Concern | Type or Runtime | Why |
|---|---|---|
| Settle-date in custody (DS1) | Type | Phantom wallet class; cheap. |
| DvP discharge atomicity (DS3) | Type | `PairedObligation` is one value; cheap. |
| Closed sum on lifecycle states / failure reasons (DS7) | Type | One sum, one match; cheap. |
| Date confusion between TradeDate / SettleDate / ValueDate / RecordDate | Type | Phantom-typed newtypes; cheap. |
| Conservation `Σ_w w_t(u) = 0` over decimal sums | Runtime | Refinement types over decimal sums require GADTs + a logic subsystem (LiquidHaskell, F\*). C2 of StatesHome chooses runtime for explicit reasons; we follow. |
| Liveness — deadline timer fires | Runtime | Wall-clock is an external input; v10.3 §11.13, data spec L_19 ClockAuthority. Encoding "this obligation must transition by time t" in the type is a category error. |
| **CSDR penalty calculation** | **Runtime** | The penalty is a function of failing party, asset class, fail duration, reference price, regulatory regime version. The type system cannot embed CSDR's full rate table without becoming the rate table. Smart-constructor on `CsdrPenaltyAccrual` validates inputs; the calculation itself is a pure function with versioned reference data. |
| **Corporate-action market-claim arithmetic** | **Runtime** | Encoding the corp-action calculus in types collapses to encoding the corp-action calculus in types — no leverage. The handler reads union of custody and obligations, weights by signed quantity, dispatches per `entitlement_capture` predicate. The predicate is bitemporal-state-function-typed (Formalis G3) but its body is runtime. |
| **Regulatory cardinality** ("at most one MiFIR report per trade per regime per day") | Runtime | Regulatory uniqueness constraints span systems. The type system can enforce "the report struct exists" but not "this regime has not yet reported this trade today". This is a database uniqueness constraint, not a type. |
| **Counterparty creditworthiness / ECL stage migration** | Runtime | Stage 1/2/3 is a function of macro signals + counterparty default proxies. Time-varying. Per-counterparty. Belongs in the credit handler, not in `Obligation.create`. |
| **Confirmation matching in absence of UTI** (Formalis G2) | Runtime, with explicit quarantine | Heuristic matching is fundamentally non-deterministic; the type system rejects ambiguous matches by routing to `L_18` BreakRegister. The contract: `match_confirmation : confirmation -> [ `Unique of Obligation.t | `Ambiguous of Obligation.t list | `Unmatched ]`; the `Ambiguous` case must be handled, not silently picked. |

**The boundary is named, not negotiated.** The first four are type-level
because the cost is one-time and the benefit is on every read site. The
last seven are runtime because the cost of type-encoding is super-linear
and the benefit does not compose.

---

## 11. What I Reject from Phase 1 Proposals on Type-Design Grounds

Six rejections, each with a reason that is local to the type-design lens.

### 11.1 Halmos / Cartan / Feynman / my-Phase-1 — `u_so` as a unit

**Rejection.** The obligation as a unit is a global change to `U`. Every
consumer of `U` (pricing, valuation, conservation, regulatory projection,
test generator universe) acquires a new constructor. The benefit — having
the obligation participate in conservation directly — is achievable with
strictly less surface area by promoting the existing virtual wallet
balance, which is *already* in `U`'s wallet algebra. Add the closed-sum
constructor on `L_15.Obligation`, not a unit class. Lattner is right: this
is library, not language.

This is the cleanest type-discipline rejection of my own Phase 1
proposal. It is also the right call.

### 11.2 Halmos's "burn a unit at extinguishment" pattern (`m_4: 1 unit of σ : B → K`)

**Rejection on type grounds, not on economics.** Halmos's mechanism is
*correct* — the σ unit issues at T, conserves through the window, burns
at discharge. The type-design objection is that "burning" is not a normal
move; it is a specially-named transaction that requires an extra
constructor in the executor's transaction-kind sum. Every other move is
"transfer between wallets". A "burn" is a different operation in the type
system, even if the algebra is the same. This is the seductive mistake of
introducing a new mechanism whose semantics are equivalent to an existing
mechanism but whose *type signature* is different. Cost: every executor
test, every property, every replay must now branch on whether a transaction
is a transfer or a burn.

The mainstream design avoids this: discharge is a virtual-to-virtual
rotation (Karpathy: `w_cpty_v → w_csd_v`), which is a normal transfer move.
No burn. No new transaction kind. The L_15 row's FSM transition carries the
"obligation has been satisfied" semantics; the move stream carries the
balance rotation.

### 11.3 Geohot / FinOps "throw the L_15 row in a separate database with denormalised snapshot"

**Rejection.** Denormalised snapshots require their own conservation proof,
their own time-travel proof, their own bitemporal restatement story. The
v10.3 framework is a closed system precisely so that one set of invariants
covers everything. Splitting state across stores creates a divergence
vector at every replication boundary. **Storage discipline is cheaper than
reconstruction discipline** (Lattner's phrasing; same point I would make).

The L_15 obligation row lives in the same closed system as the move stream.
Its FSM is part of the StatesHome 3-map ruling. No second database.

### 11.4 Any proposal that lets a string flow through as a settlement status

This catches several Phase 1 proposals that left `lifecycle_stage` as
`String` in their pseudo-code. Jane Street caught the `"setled"` example in
production. The discipline is: every status-bearing field is a closed sum,
construction goes through a smart constructor, and the test generator walks
the variants. No exceptions for "convenience" or "compatibility with the
upstream messaging library".

### 11.5 Lattner's "Option B: bundle obligations into the position read API"

Lattner himself rejects this, but it is worth pinning the type-design
argument for the record. Bundling produces `position : Wallet -> Unit ->
(ScalarOrVector, List[Obligation])`. Every consumer pays the join cost.
Worse: the join's *type* fixes the cardinality of obligations per
(wallet, unit), and any future extension that wants per-trade obligations
versus per-leg obligations versus per-counterparty obligations forces an
API change. Keep the queries separate. Compose at the call site if you
need both.

### 11.6 Nazarov / Grothendieck "represent the obligation as a category morphism"

The categorical framing is interesting and may have value as documentation,
but the *type design* must be implementable in the actual implementation
language (OCaml-flavoured per corpus convention). Categorical structures
do not survive codegen on Decimal sums and on Temporal workflow histories.
The discipline is to encode what is cheap to encode and to write down what
is not. A category-theoretic design that the type-checker cannot enforce is
documentation, not a type.

I do not reject the category-theoretic insight — the obligation FSM is a
monoid, the discharge is a morphism, and the cross-currency case is a
product in the obligation category. These are real. They guide the design.
But they do not *replace* the closed-sum, smart-constructor, phantom-typed
discipline. They are dual to it.

---

## 12. Migration Strategy — From v10.3 Runtime Validation to v11.0 Type Discipline

The existing v10.3 codebase uses `UnitStatus.lifecycle_stage` as a string
field with runtime validation. The migration is staged so that no point in
the migration path produces a system worse than what we have today.

### Stage 0: discovery (1 week)

- Inventory all sites that read or write `lifecycle_stage`. Greppable
  because it is a field on `UnitStatus`.
- Inventory all sites that mutate real wallets via settlement-confirmation
  paths. Audit: any of these that take a `wallet_id` rather than a
  `wallet_handle` is migration-blocking.
- Inventory all uses of raw `Date.t` as settlement dates. Audit: any of
  these is a candidate for the newtype-date refactor.

### Stage 1: introduce types alongside strings (3 weeks, 1 engineer)

- Add the `lifecycle` closed sum to `UnitStatus` as a *new field*
  alongside the existing `lifecycle_stage : string`. Both are written;
  the closed sum is the source of truth; the string is derived from it
  (`to_string : lifecycle -> string`) and kept for backward compatibility
  with downstream consumers that still parse strings.
- Add the `step` function. Wire it into the existing handler at the
  ingest of `sese.024 / sese.025` messages. The handler updates both the
  closed-sum field and the string field; a property test asserts they are
  in sync.
- Add `creation_error` as a closed sum and refactor `Obligation.create`
  to return `Result.t` instead of raising. Existing callers wrap the
  result in `unwrap` for one release; after that they handle errors
  explicitly.

After Stage 1, the type discipline is *available* everywhere; the runtime
validation is still the source of truth in the critical path. No behavioral
change. Production-safe.

### Stage 2: flip the source of truth (4 weeks, 2 engineers)

- Switch the lifecycle FSM's source of truth from the string to the
  closed sum. The string becomes derived. Downstream consumers that read
  the string keep working; consumers that read the closed sum get the new
  type discipline. A migration property test asserts byte-equivalence
  between the two views on every replayed event.
- Refactor every transition site to consume `transition_result` instead
  of mutating in place. Compiler errors at every call site that ignored
  a `Reject` constructor — these are the latent bugs.
- Introduce `wallet_handle` phantom types. Migration is by
  search-and-replace at the wallet construction sites: every place that
  creates a real wallet now creates a `real_wallet wallet_handle`. The
  type checker finds every site that confused real and virtual.

After Stage 2, the type discipline enforces the trade-date / settlement-
date split at the type level. Existing string-based downstream consumers
keep working. The migration is observable but not breaking.

### Stage 3: introduce paired-obligation discharge (2 weeks, 1 engineer)

- Add the `PairedObligation` module with `pair` constructor and
  `discharge` function.
- Refactor the discharge handler to consume `PairedObligation.t`. Existing
  per-leg discharge functions become deprecated and emit a runtime
  warning.
- Property test: every discharge in the previous 90 days of replay
  produces an identical move stream under the new mechanism.

### Stage 4: introduce newtype dates (3 weeks, 1 engineer)

- Add `TradeDate`, `SettleDate`, `ValueDate`, `RecordDate` modules.
- Refactor `Obligation.create` to take typed dates. Refactor the
  settlement projection (v10.3 §8.1) to read typed dates.
- Migration of upstream date producers: most date sources are at the
  ingestion boundary (FIX execution reports, ISO 20022 messages). The
  ingestion boundary is the right place to construct the typed date with
  validation; downstream code reads typed dates.

After Stage 4, settle-date confusion is a type error.

### Stage 5: deprecate strings, remove runtime validation (1 week)

- Delete the `lifecycle_stage : string` field from `UnitStatus`. Every
  consumer now reads the closed sum.
- Delete the runtime-validation paths for malformed obligation
  construction. The type system enforces them; the runtime-checks become
  dead code.

### Stage 6: turn on warning-as-error (1 day)

- Compile the entire codebase with `-warn-error +partial-match`.
  Inexhaustive matches were a soft warning; they become build-breaking.
  Every match site is now provably exhaustive.

**Total: ~14 weeks, 1–2 engineers depending on stage.** Comparable to
Jane Street's 18-week implementation plan but with type discipline carved
out as a parallel workstream that does not block the obligation-row
deliverable.

The migration produces no behavioral change in production (Stages 1–4 are
type-additive; Stages 5–6 remove dead code). The benefit is that every
class of bug listed in §1.4 of my Phase 1 proposal becomes structurally
impossible after Stage 4, not after a future production incident.

---

## 13. The Six-Question Minsky Test, Applied to the Final Design

1. **Can illegal states be constructed?** No. Smart constructor rejects 14
   malformed-obligation cases. Phantom-typed wallet handles prevent
   cross-class moves. `PairedObligation` makes partial discharge
   unrepresentable. Closed sums make typo'd statuses uncompilable.

2. **Is every case handled?** Yes. The lifecycle FSM is a closed sum;
   `step` is total; pattern-match exhaustiveness as compile error.
   `transition_result` makes every `(state, event)` pair an explicit
   `Step`, `Reject`, or `Idempotent`.

3. **Is failure explicit?** Yes. `Result.t` everywhere. `failure_reason`
   is a closed sum; `creation_error` is a closed sum; `discharge_error`
   is a closed sum; `pairing_error` is a closed sum; `reject_reason` is
   a closed sum.

4. **Would a reviewer catch a bug by reading?** Yes. The discharge
   function is one place. The lifecycle FSM is one match. The smart
   constructor enumerates every malformation at construction.

5. **Are invariants encoded or documented?** Encoded at the type level:
   DS1 (no custody before settle), DS3 (DvP discharge atomicity at the
   leg pair), date discipline, status discipline. Documented as runtime
   invariants: DS2 (decimal-sum conservation), DS4 (workflow liveness),
   DS-CA (corp-action entitlement), CSDR penalty calculation.

6. **Is this total?** Yes. Every public function returns `Result.t` or
   pattern-matches exhaustively. No partial functions. No raised
   exceptions on the happy path.

---

## 14. Summary

I withdraw `u_so`. The mainstream design is right: virtual wallets carry
the open obligation balance, `L_15.Obligation` carries the lifecycle FSM
and discharge predicate, the transaction-level FSM is a property of the
obligation row, not of the unit. There is no fourth state map and no new
unit class.

The type discipline is non-negotiable and applies intact:

- the lifecycle FSM is a closed sum with carried evidence per state and a
  total `step` function that returns `Step | Reject | Idempotent`;
- `PairedObligation` makes DvP discharge atomic by structure, not by
  transaction-level convention;
- phantom-typed wallet handles (`real_wallet`, `cpty_virtual_wallet`,
  `csd_virtual_wallet`) make DS1 a type error to violate;
- newtype dates (`TradeDate`, `SettleDate`, `ValueDate`, `RecordDate`)
  make trade-date / settlement-date confusion a type error;
- the smart constructor `Obligation.create` rejects 14 malformed cases at
  construction;
- accounting-basis projections are phantom-typed (`trade_date_basis` vs
  `settle_date_basis`), so the framework's default basis is unambiguous
  by type;
- cross-currency Herstatt is a tuple of two `PairedObligation`s with
  asymmetric `SettleDate`s — non-atomicity is *visible in the type*.

Conservation, liveness, corp-action entitlement, CSDR penalty, ECL stage
migration, and confirmation-matching ambiguity remain as runtime
obligations, named explicitly. The boundary between type-level and
runtime-level enforcement is documented, not negotiated.

The migration is staged, type-additive in the first four stages, and
removes runtime validation only after the type discipline is the source of
truth. No behavioral change in production at any stage; the benefit is
that the bugs that survive cannot be the trade-date / settlement-date
confusion that this whole specification is designed to prevent.

**Adopt the mainstream representation. Adopt this discipline on top of
it. Make the compiler refuse to skip T+2.**

— MINSKY, Phase 2 Settlement Team, type-design discipline, 2026-04-30.
