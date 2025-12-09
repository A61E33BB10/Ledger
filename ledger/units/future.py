"""
future.py - Exchange-Traded Futures with Daily Mark-to-Market

Supports negative prices (oil went to -$37 during COVID).

=== THE VIRTUAL CASH MODEL ===

Per-wallet state:
    position: Net contracts held (redundant with ledger balance, for validation)
    virtual_cash: Sum of (-qty * price * mult) for all trades
                  This is the "cash spent" to acquire the position.

At any moment:
    economic_value = virtual_cash + position * current_price * mult

On TRADE at price P:
    - Position moves between wallet and clearinghouse
    - virtual_cash -= qty * P * mult  (you pay/receive cash for the trade)

On MTM at price P:
    - target_vcash = -position * P * mult  (what vcash WOULD be if all trades were at P)
    - vm = virtual_cash - target_vcash     (settle the difference)
    - virtual_cash = target_vcash          (reset to target)

This is equivalent to settling position * (P - avg_entry_price) * mult,
but without tracking avg_entry_price explicitly.
"""
from __future__ import annotations
import math
from datetime import datetime, date
from typing import Dict
from ..core import LedgerView, Move, ContractResult, Unit, QUANTITY_EPSILON, UNIT_TYPE_FUTURE


def create_future(
    symbol: str, name: str, underlying: str, expiry: datetime,
    multiplier: float, currency: str, clearinghouse: str,
) -> Unit:
    """Create a futures contract."""
    if multiplier <= 0:
        raise ValueError(f"multiplier must be positive, got {multiplier}")
    if not clearinghouse or not clearinghouse.strip():
        raise ValueError("clearinghouse cannot be empty")
    return Unit(
        symbol=symbol, name=name, unit_type=UNIT_TYPE_FUTURE,
        min_balance=-1_000_000.0, max_balance=1_000_000.0, decimal_places=2,
        _state={'underlying': underlying, 'expiry': expiry, 'multiplier': multiplier,
                'currency': currency, 'clearinghouse': clearinghouse,
                'last_settle_price': None, 'last_settle_date': None, 'settled': False,
                'wallets': {}})


def transact(view: LedgerView, symbol: str, wallet: str, qty: float, price: float) -> ContractResult:
    """
    Execute a futures trade. Algebraic qty: positive=buy, negative=sell.

    virtual_cash -= qty * price * mult
    (Positive qty = buy = you spend cash, negative qty = sell = you receive cash)
    """
    state = view.get_unit_state(symbol)
    if state.get('settled'):
        raise ValueError(f"Cannot trade settled contract {symbol}")
    if abs(qty) < QUANTITY_EPSILON:
        raise ValueError(f"qty must be non-zero, got {qty}")
    if not math.isfinite(price):
        raise ValueError(f"price must be finite, got {price}")

    ch = state['clearinghouse']
    if wallet == ch:
        raise ValueError("wallet cannot be clearinghouse")

    mult = state['multiplier']
    wallets = dict(state.get('wallets', {}))
    w_state = wallets.get(wallet, {})

    # Track position in state (defense-in-depth: validates ledger consistency)
    old_pos = w_state.get('position', 0.0)
    ledger_pos = view.get_balance(wallet, symbol)
    if abs(old_pos - ledger_pos) >= QUANTITY_EPSILON:
        raise ValueError(f"Position mismatch for {wallet}: state={old_pos}, ledger={ledger_pos}")
    new_pos = old_pos + qty

    # Validate position limits
    unit = view.get_unit(symbol)
    if new_pos < unit.min_balance:
        raise ValueError(f"Position {new_pos} would exceed min_balance {unit.min_balance} for {wallet}")
    if new_pos > unit.max_balance:
        raise ValueError(f"Position {new_pos} would exceed max_balance {unit.max_balance} for {wallet}")

    # virtual_cash accumulates -qty * price * mult for each trade
    old_vcash = w_state.get('virtual_cash', 0.0)
    vcash_change = -qty * price * mult
    new_vcash = old_vcash + vcash_change

    wallets[wallet] = {'position': new_pos, 'virtual_cash': new_vcash}

    # Clearinghouse state update (defense-in-depth: validates ledger consistency)
    ch_state = wallets.get(ch, {})
    ch_old_pos = ch_state.get('position', 0.0)
    ch_ledger_pos = view.get_balance(ch, symbol)
    # Only validate if CH already has state entry (tests may initialize CH ledger balance directly)
    if ch in wallets and abs(ch_old_pos - ch_ledger_pos) >= QUANTITY_EPSILON:
        raise ValueError(f"Position mismatch for {ch}: state={ch_old_pos}, ledger={ch_ledger_pos}")
    ch_new_pos = ch_ledger_pos - qty  # Use ledger position as source of truth
    wallets[ch] = {'position': ch_new_pos, 'virtual_cash': ch_state.get('virtual_cash', 0.0) - vcash_change}

    src, dst, q = (ch, wallet, qty) if qty > 0 else (wallet, ch, -qty)
    return ContractResult(
        moves=(Move(source=src, dest=dst, unit=symbol, quantity=q, contract_id=f'future_{symbol}'),),
        state_updates={symbol: {**state, 'wallets': wallets}})


def mark_to_market(
    view: LedgerView, symbol: str, price: float, settle_date: date | None = None
) -> ContractResult:
    """
    Mark all positions to market.

    For each wallet:
        target_vcash = -position * price * mult  (what vcash WOULD be at this price)
        vm = virtual_cash - target_vcash         (the difference is the settlement)
        virtual_cash = target_vcash              (reset)

    Positive vm = trader receives cash, negative = trader pays.

    Note: We settle wallets with positions OR with virtual_cash (to handle
    wallets that closed their position but haven't been settled yet).
    """
    state = view.get_unit_state(symbol)
    if state.get('settled'):
        raise ValueError(f"Cannot mark-to-market settled contract {symbol}")
    if not math.isfinite(price):
        raise ValueError(f"price must be finite, got {price}")
    if settle_date and state.get('last_settle_date') == settle_date:
        return ContractResult()  # Idempotent

    mult, currency, ch = state['multiplier'], state['currency'], state['clearinghouse']
    positions = view.get_positions(symbol)
    wallets = dict(state.get('wallets', {}))
    moves = []

    # Settle all wallets that have either a position or virtual_cash
    wallets_to_settle = set(positions.keys()) | set(wallets.keys())

    for w in sorted(wallets_to_settle):
        pos = positions.get(w, 0.0)
        w_state = wallets.get(w, {})
        vcash = w_state.get('virtual_cash', 0.0)
        state_pos = w_state.get('position', 0.0)

        # Validate position consistency (defense-in-depth)
        if w in wallets and abs(state_pos - pos) >= QUANTITY_EPSILON:
            raise ValueError(f"Position mismatch for {w}: state={state_pos}, ledger={pos}")

        # Skip if nothing to settle
        if abs(pos) < QUANTITY_EPSILON and abs(vcash) < QUANTITY_EPSILON:
            continue

        target_vcash = -pos * price * mult
        vm = vcash - target_vcash

        # Skip move creation for clearinghouse: Move requires src != dest,
        # and CH settlement is already reflected in the bilateral moves with traders
        if abs(vm) > QUANTITY_EPSILON and w != ch:
            src, dst, q = (ch, w, vm) if vm > 0 else (w, ch, -vm)
            moves.append(Move(
                source=src, dest=dst, unit=currency, quantity=q,
                contract_id=f'mtm_{symbol}_{w}',
                metadata={'note': f'MTM {symbol} at {price}'}
            ))

        # Reset or remove wallet state
        if abs(pos) < QUANTITY_EPSILON:
            # Position is zero, clear the wallet state entirely
            wallets.pop(w, None)
        else:
            wallets[w] = {'position': pos, 'virtual_cash': target_vcash}

    new_state = {**state, 'wallets': wallets, 'last_settle_price': price, 'last_settle_date': settle_date}
    return ContractResult(moves=tuple(moves), state_updates={symbol: new_state})


def future_contract(
    view: LedgerView, symbol: str, timestamp: datetime, prices: Dict[str, float]
) -> ContractResult:
    """SmartContract: daily MTM and expiry. Called by LifecycleEngine."""
    state = view.get_unit_state(symbol)
    if state.get('settled'):
        return ContractResult()
    price = prices.get(state.get('underlying'))
    if price is None:
        return ContractResult()

    result = mark_to_market(view, symbol, price, settle_date=timestamp.date())

    if state.get('expiry') and timestamp >= state['expiry']:
        updated = {**result.state_updates.get(symbol, state), 'settled': True, 'settlement_price': price}
        return ContractResult(moves=result.moves, state_updates={symbol: updated})
    return result
