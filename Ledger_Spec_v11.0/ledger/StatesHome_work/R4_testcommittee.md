# R4 — TESTCOMMITTEE: Adversarial Re-review (Testability)

*Tests are the specification. If a property is awkward to state, the representation is wrong.*

The four-map scheme under test: `ProductTerms[u]` (immutable), `UnitStatus[u]`, `WalletState[w]`, `PositionState[w, u]`. Unresolved axis: `PositionState` as `Option<PS>` (None when never traded) vs `Monotone` (create-on-first-touch, `(0,0)` after close-out, never GC'd).

## 1. Property-Based Testing

### 1.1 Conservation — `Σ_w ac(w, u) = 0`

```python
@given(events=st.lists(event_gen(wallets=wallet_pool, units=unit_pool),
                       max_size=200))
@settings(max_examples=500, deadline=None)
def test_conservation(events):
    view = apply_all(View.empty(), events)
    for u in view.units_touched():
        total = sum(ps.accumulated_cost
                    for (w, u2), ps in view.status_wu.items()
                    if u2 == u)
        assert total == Decimal(0), f"u={u}: Σac={total}"
```

**Generator choice.** `event_gen` emits `Trade(w_buy, w_sell, u, qty, px)` with `w_buy != w_sell` and `u ∈ unit_pool` (fixed pool ⇒ shrinking converges); MTM settlements as pure `u`-events that do not touch `ac`; close-outs are trades into flatness, not a distinct event.

**Option vs Monotone.** **Monotone is strictly easier.** Under Option, the sum must iterate `status_wu.values()` and also **reconstruct** `(w, u)` pairs that went through `Some → None` if close-outs GC. That requires either replay or a shadow set. Under Monotone every `(w, u)` ever touched has a live row with `ac=0` after close-out, and the sum is a single pass over a stable key set. Shrinking is also cleaner: the minimal counterexample is a sequence of trades, not "trade + close + re-open" whose GC semantics pollute the failure.

### 1.2 Idempotency

```python
@given(events=st.lists(event_gen(), max_size=100),
       dup_index=st.integers(min_value=0))
def test_idempotency(events, dup_index):
    if not events: return
    i = dup_index % len(events)
    v1 = apply_all(View.empty(), events)
    v2 = apply_all(View.empty(),
                   events[:i+1] + [events[i]] + events[i+1:])
    assert v1 == v2
```

This requires events to carry an `event_id` and the core to de-duplicate. **Option makes idempotency harder to state**: observational equality of `v1` and `v2` must treat `None` and `Some(zero)` as *distinguishable* (Lattner's rule) yet *equal-modulo-duplicate-close-out*. Under Monotone the equality is structural on `status_wu` dicts — one line. Under Option you need a normalisation function `canon(view)` that collapses the distinction, which is exactly the coupling Feynman's gauge argument warns against.

### 1.3 Determinism (replay from checkpoint)

```python
@given(events=st.lists(event_gen(), min_size=1, max_size=300),
       cut=st.integers(min_value=0))
def test_replay_determinism(events, cut):
    k = cut % (len(events) + 1)
    full = apply_all(View.empty(), events)
    ck   = apply_all(View.empty(), events[:k])
    resumed = apply_all(ck, events[k:])
    assert full == resumed
```

**Feynman's hammer lands here.** Under Option with GC-on-flat, `events[:k]` may end with a live `(0,0)`, while `full` may end with `None` — same trajectory, different state. The test fails not on a bug but on a representation artefact. Under Monotone the trajectory is functorial: `apply_all` is a left fold, and fold-associativity is preserved. **Monotone makes replay determinism a one-line property; Option requires a canonicalisation lemma.**

**Ruling on §1: Monotone on all three counts.**

## 2. Differential Testing v10.3 ↔ 4-map

v10.3: per-unit dict `unit_state[u]` with a nested `holders` map, plus per-`(w,u)` futures cost dict.

**Forward** `F`: split `unit_state[u]` into `ProductTerms[u]` (static) + `UnitStatus[u]` (mutable scalars) + `{(w,u) → PS}` extracted from `holders`; `WalletState` from existing managed-account record.
**Inverse** `F⁻¹`: merge `ProductTerms[u] ∪ UnitStatus[u]` into v10.3's `unit_state[u]`; for each `(w,u) ∈ status_wu`, insert `holders[w] = ps` on v10.3's unit row; re-embed `WalletState`.

**States in new not reachable from v10.3.** Yes: new scheme admits `status_w[w]` for wallets with *no* unit touch (pure mandate). v10.3 had no home for this (Minsky's original complaint). These are *intended* new states; migration is surjective only onto the legal v10.3 subset.

**States in v10.3 not reachable from new.** Yes, the illegal ones: two holders of `u` with *different* `last_settle_price` (v10.3 has no type-level preventer inside `holders`). The new scheme rejects these by construction. Migration is *lossy on illegal states*, which is correct.

**Lossless migration test** (restricted to legal v10.3 states):

```python
@given(v=legal_v103_view())
def test_migration_roundtrip(v):
    assert F_inv(F(v)) == v
@given(events=st.lists(event_gen()))
def test_behavioural_equivalence(events):
    v103 = run_v103(events); v4 = run_v4map(events)
    for obs in OBSERVABLES:          # balances, ac, HWM, last_settle, fees
        assert obs(v103) == obs(F_inv(v4))
```

Both must pass on the full regression corpus.

## 3. Fault Injection

**Partial writes.** Unit Store succeeds, `PositionState` write fails. The four-map scheme **forces a single atomic `StateDelta`** (Lattner §2) applied transactionally; partial writes must be impossible by construction. Test: inject an IOError after `status_u` write; assert the in-memory view is unchanged AND no on-disk record of `status_u` mutation exists. Monotone and Option are equivalent here — atomicity is at the delta layer, orthogonal to the representation axis.

**Event storm on one `(w,u)`.** 10⁴ trades on the same pair, random quantities summing to net flat. Mutation score expectation: **≥ 85%** — the handlers are tiny (add/subtract on Decimal) and the invariant (`Σac=0`) kills most arithmetic mutants. Survivors are predictable: `>` vs `>=` on lifecycle guards, commutativity-exploiting reorder mutants that conservation can't catch.

**Close-out then reopen.** Under Option: `None → Some → None → Some` — fresh state, second Some starts at zero, no history. Under Monotone: `(0,0) → (+q, -qpM) → (0,0) → (+q', -q'pM)` — `ac` cycles through zero but a `last_trade_date` residue survives. **Is the residue a feature?** For fault injection, **yes, feature.** The residue is an auditable footprint: a replayed close-and-reopen leaves a trail the ledger operator can diff against external records. Under Option the second open is indistinguishable from a first open — a genuine fault (e.g. a replay attack that "resets" a wallet's history) cannot be detected from state alone. **Monotone is the more testable fault substrate.**

## 4. State-Machine Spec (TLA+-style, futures family)

```
VARIABLES status_u, status_wu, events_applied
Init == status_u = [u \in Units |-> [ls |-> "LISTED", last_settle |-> NULL]]
     /\ status_wu = << >>      \* empty partial function
     /\ events_applied = {}

Trade(w1, w2, u, q, p) ==
    LET m == ProductTerms[u].multiplier
        d == q * p * m
    IN  status_wu' = status_wu @@
          (w1, u) :-> [ac |-> ac(w1,u) - d]  @@
          (w2, u) :-> [ac |-> ac(w2,u) + d]

Settle(u, s) == status_u' = [status_u EXCEPT ![u].last_settle = s]

Inv_Conservation ==
    \A u \in Units : SumOver(w \in Wallets, ac(w,u)) = 0
Inv_TotalQty ==
    \A u \in Units : SumOver(w \in Wallets, net_qty(w,u)) = 0
```

**Reachable states.** With `|W|=3`, `|U|=2`, `|events|≤6`, bounded quantities `{-2..2}`, prices `{100, 110}`: TLC explores ~10⁵–10⁶ states (fanout of Trade dominates). Tractable.

**Does TLC catch a handler that violates conservation?** Yes, trivially: flip `+d` to `+d + 1` and TLC reports the first trace at depth 1. That is the acceptance test for the model.

## 5. Final Verdict

- **Ship: yes**, the 4-map scheme with Feynman/Lattner refinements.
- **`PositionState`: Monotone.** Three property signatures get shorter; replay determinism becomes a fold identity; close-and-reopen leaves an auditable residue fault-injection can exploit. Option's "never-held vs held-and-flat" distinction is real but belongs in a sibling boolean (`ever_touched`), not in the presence/absence of the row.
- **4-map over 3-map.** Separating `ProductTerms` (immutable) from `UnitStatus` (mutable) is what allows the idempotency property to be stated structurally — immutable fields are automatically invariant under replay.
- **Mutation score expectation: 85–90%** on handlers, 70–80% on lifecycle guards. Survivors clustered around ordering/commutativity; catch them with a linearisability test (QuickCheck `Sequential` → `Parallel`).

*The representation that makes the properties shortest is the representation that is true.*
