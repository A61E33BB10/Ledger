# R3 — KARPATHY: Where State Lives, From Scratch

*Rebuild the argument. Do not trust the R1/R2 framing. Ask: what is state, physically?*

## 1. First principles

State is the **minimum information, beyond balances $w_t(u)$ and market data $m_t$, needed to price, roll, and settle every position going forward.** Anything derivable from balances + moves + market data is not state.

Two axes are *given*: `U` (contracts) and `W` (wallets). A field is a function of some subset of `{u, w}` — three choices: `s(u)`, `s(w)`, `s(w,u)`. A field belongs on the axis of the variables it actually varies over. This is the substitution rule, not category theory. If `s` doesn't mention `w`, keying by `w` is a redundancy bug; if it mentions both, keying by only one loses information.

## 2. The worked example

**Setup.** Manager **A** runs "MomoQIS" on behalf of client **C**. The QIS trades three futures: **ES** at CME, **NQ** at CME, **FESX** at Eurex. A is benchmarked to SPXTR with a 70% NAV barrier.

**Wallets.** `w_C`, `w_A`, `w_Q` (QIS exec), `w_CME`, `w_EUREX`.
**Units.** `u_Q`, `u_ES`, `u_NQ`, `u_FESX`.

### Field-by-field taxonomy

| Field | Varies over | Home | Why |
|---|---|---|---|
| `u_ES.multiplier = 50` | `u` | `U` | Exchange sets one value. |
| `u_ES.lifecycle_stage` | `u` | `U` | All holders see the same ACTIVE/EXPIRED. |
| `u_ES.last_settlement_price` | `u` | `U` | CME publishes one number per contract per day; per-wallet copies invite drift. |
| `u_Q.{rule_id, universe, rebalance_schedule, barrier=0.7, benchmark=SPXTR}` | `u` | `U` | Strategy definition is shared; not per-subscriber. |
| `u_Q.{current_weights, last_rebalance_date, triggered_barrier}` | `u` | `U` | One strategy, one weight vector. Divergence would mean different strategies. |
| `w_C.HWM`, `w_C.accrued_mgmt_fee`, `w_C.accrued_perf_fee`, `w_C.mandate_flags`, `w_C.benchmark_nav_baseline` | `w` | `W` | HWM is a scalar over the *account's* performance. `u` does not appear in its definition. |
| `ac(w_Q, u_ES)` | `(w, u)` | `P` | Different wallets trading ES have genuinely different cost bases. The invariant `Σ_w ac(w, u_ES) = 0` is expressible *only* as a sum over `w` at fixed `u`. |
| `ac(w_Q, u_NQ)`, `ac(w_Q, u_FESX)` | `(w, u)` | `P` | Same. FESX routes through Eurex, not CME — the CCP binding lives in `P` because two wallets can route the same contract through different CCPs (v10.3 line 1168). |
| Client's subscription balance in MomoQIS | `w_C(u_Q)` | **ledger balance** | Not state. Base layer. |

### Minimality: all three sectors required

- Delete `U`: `last_settlement_price` moves to `(w, u)`. Every settlement atomically writes across every wallet holding ES; nothing prevents A and B from disagreeing on today's close.
- Delete `W`: C's HWM has no home. Pinning it to `(w_C, u_Q)` means a second strategy `u_Q'` gives C two HWMs. HWM belongs to the mandate, which lives on the wallet.
- Delete `P`: `Σ_w ac(w, u) = 0` cannot be written. Futures collapse.

No proper subset works. **Three sectors necessary.**

### Sufficiency on the four canonical cases

1. **Futures** — `P(w, u_ES).ac` + `U(u_ES).{last_settle_price, lifecycle_stage, multiplier}`.
2. **Managed account** — `W(w_C).{HWM, mandate, fees}`. No synthetic `u_∅` (rejects Dirac).
3. **QIS trading futures** — `U(u_Q)` strategy, `P(w_Q, u_ES)` legs, `W(w_C)` mandate. Stratified cleanly.
4. **Untraded listed unit** — `U(u)` only; `P`, `W` empty for this `u`. Lifecycle totality preserved.

**Three sectors sufficient.** Not over-complete: each sector catches a field no other can.

## 3. Verdict

The converging proposal — `UnitState[u]` / `WalletState[w]` / `PositionState[w,u]`, `(w,u)` primary mutable, `u` immutable template, `w` managed-account-shaped — is **necessary, sufficient, not over-complete**, with two corrections from R2:

1. **Invariants live in event handlers, not storage.** `Σ_w ac = 0` is a *theorem* by induction on per-trade zero-sum (`buyer_delta + seller_delta = 0`). Storage makes it *expressible*; handlers make it *true*. (Formalis, Jane Street, Minsky all converge here.)
2. **Split static product terms from mutable unit state.** `multiplier`, `currency`, `expiry` immutable at registration (Unit Store `product_terms`); `lifecycle_stage`, `last_settlement_price`, `paid_coupons` mutable (`U(u)` proper). One store, two types.

Reject the Grothendieck sheaf (no operational commitment), the Dirac `u_∅` device (breaks conservation; sentinel ops debt), and the Rosetta "ban W-state" edict (over-fitted to OTC).

## 4. Implementation sketch (~30 lines)

```python
# Three total accessors. Each keyed by the free variables of its fields.
# Invariants are discharged in handlers, not storage.

@dataclass(frozen=True)
class UnitState:                      # keyed by u
    product_terms: ProductTerms       # immutable after registration
    lifecycle_stage: Stage            # ACTIVE | EXPIRED | SETTLED
    mutable: ProductUnitState         # paid_coupons, last_settle_price, QIS weights

@dataclass(frozen=True)
class WalletState:                    # keyed by w
    mandate: Mandate | None           # HWM, benchmark, fee schedule, breach flags
    fee_accruals: FeeAccruals

@dataclass(frozen=True)
class PositionState:                  # keyed by (w, u)
    product_state: ProductPosState    # FuturesAccCost, CCPBinding

class View:
    def get_unit(self, u: Uid) -> UnitState: ...          # total; default at registration
    def get_wallet(self, w: Wid) -> WalletState: ...      # total; default for non-managed
    def get_position(self, w: Wid, u: Uid) -> PositionState | None: ...  # None = never traded

def apply_trade(tx, w_buy, w_sell, u, q, p):
    mult = tx.get_unit(u).product_terms.multiplier
    d_buy, d_sell = -q * p * mult, +q * p * mult
    assert d_buy + d_sell == 0        # structural zero-sum. This is how Σ_w ac = 0 holds.
    tx.update_position(w_buy,  u, lambda s: s.add_ac(d_buy))
    tx.update_position(w_sell, u, lambda s: s.add_ac(d_sell))
```

Three maps. One invariant, proved at the handler. No sentinels. Ship it.
