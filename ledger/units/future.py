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
from ..core import (
    LedgerView, Move, PendingTransaction, Unit, UnitStateChange, QUANTITY_EPSILON, UNIT_TYPE_FUTURE,
    build_transaction, empty_pending_transaction,
)


def create_future(
    symbol: str, name: str, underlying: str, expiry: datetime,
    multiplier: float, currency: str, clearinghouse_id: str,
) -> Unit:
    """Create a futures contract."""
    if multiplier <= 0:
        raise ValueError(f"multiplier must be positive, got {multiplier}")
    if not clearinghouse_id or not clearinghouse_id.strip():
        raise ValueError("clearinghouse_id cannot be empty")
    return Unit(
        symbol=symbol, name=name, unit_type=UNIT_TYPE_FUTURE,
        min_balance=-1_000_000.0, max_balance=1_000_000.0, decimal_places=2,
        _state={'underlying': underlying, 'expiry': expiry, 'multiplier': multiplier,
                'currency': currency, 'clearinghouse': clearinghouse_id,
                'last_settle_price': None, 'last_settle_date': None, 'settled': False,
                'wallets': {}})


def transact(
    view: LedgerView,
    symbol: str,
    seller_id: str,
    buyer_id: str,
    qty: float,
    price: float,
) -> PendingTransaction:
    """
    Execute a futures trade.

    Handles three cases:
        1. seller_id == CH: Exchange trade, buyer opens long (CH sells to buyer)
        2. buyer_id == CH: Exchange trade, seller opens short (seller sells to CH)
        3. Neither is CH: Bilateral trade via clearinghouse (seller -> CH -> buyer)

    In all cases, the clearinghouse intermediates. Virtual cash updates:
        - Seller: virtual_cash += qty * price * mult (receives value)
        - Buyer: virtual_cash -= qty * price * mult (pays value)

    Args:
        view: LedgerView for reading state
        symbol: Futures contract symbol
        seller_id: Wallet ID selling (can be clearinghouse for long entry)
        buyer_id: Wallet ID buying (can be clearinghouse for short entry)
        qty: Quantity to trade (must be positive)
        price: Price per contract (can be negative for commodities)

    Returns:
        PendingTransaction with moves and updated wallet states
    """
    state = view.get_unit_state(symbol)
    if state.get('settled'):
        raise ValueError(f"Cannot trade settled contract {symbol}")
    if qty <= 0:
        raise ValueError(f"qty must be positive, got {qty}")
    if not math.isfinite(price):
        raise ValueError(f"price must be finite, got {price}")

    ch_id = state['clearinghouse']
    if seller_id == buyer_id:
        raise ValueError("seller and buyer must be different")
    if seller_id == ch_id and buyer_id == ch_id:
        raise ValueError("clearinghouse cannot be both seller and buyer")

    mult = state['multiplier']
    wallet_states = dict(state.get('wallets', {}))
    unit = view.get_unit(symbol)

    # Helper to update wallet state
    def update_wallet(wallet_id: str, position_delta: float, vcash_delta: float):
        wallet_state = wallet_states.get(wallet_id, {})
        state_position = wallet_state.get('position', 0.0)
        ledger_position = view.get_balance(wallet_id, symbol)

        # Defense-in-depth: validate state matches ledger
        if wallet_id in wallet_states and abs(state_position - ledger_position) >= QUANTITY_EPSILON:
            raise ValueError(f"Position mismatch for {wallet_id}: state={state_position}, ledger={ledger_position}")

        new_position = state_position + position_delta

        # Validate position limits (skip for clearinghouse - it's exempt)
        if wallet_id != ch_id:
            if new_position < unit.min_balance:
                raise ValueError(f"Position {new_position} would exceed min_balance {unit.min_balance} for {wallet_id}")
            if new_position > unit.max_balance:
                raise ValueError(f"Position {new_position} would exceed max_balance {unit.max_balance} for {wallet_id}")

        old_vcash = wallet_state.get('virtual_cash', 0.0)
        wallet_states[wallet_id] = {'position': new_position, 'virtual_cash': old_vcash + vcash_delta}

    value = qty * price * mult

    # Determine trade type and create moves
    match (seller_id == ch_id, buyer_id == ch_id):
        case (True, False):
            # Exchange trade: CH sells to buyer (buyer opens/increases long)
            update_wallet(ch_id, -qty, +value)
            update_wallet(buyer_id, +qty, -value)
            moves = [Move(quantity=qty, unit_symbol=symbol, source=ch_id, dest=buyer_id,
                         contract_id=f'future_{symbol}_buy_{buyer_id}')]

        case (False, True):
            # Exchange trade: seller sells to CH (seller opens/increases short)
            update_wallet(seller_id, -qty, +value)
            update_wallet(ch_id, +qty, -value)
            moves = [Move(quantity=qty, unit_symbol=symbol, source=seller_id, dest=ch_id,
                         contract_id=f'future_{symbol}_sell_{seller_id}')]

        case (False, False):
            # Bilateral trade: seller -> CH -> buyer (CH net position unchanged)
            update_wallet(seller_id, -qty, +value)
            update_wallet(buyer_id, +qty, -value)
            ch_wallet_state = wallet_states.get(ch_id, {})
            ch_ledger_position = view.get_balance(ch_id, symbol)
            wallet_states[ch_id] = {'position': ch_ledger_position, 'virtual_cash': ch_wallet_state.get('virtual_cash', 0.0)}
            moves = [
                Move(quantity=qty, unit_symbol=symbol, source=seller_id, dest=ch_id,
                     contract_id=f'future_{symbol}_sell_{seller_id}'),
                Move(quantity=qty, unit_symbol=symbol, source=ch_id, dest=buyer_id,
                     contract_id=f'future_{symbol}_buy_{buyer_id}'),
            ]

        case (True, True):
            # Already guarded above, but explicit for completeness
            raise ValueError("clearinghouse cannot be both seller and buyer")

    new_state = {**state, 'wallets': wallet_states}
    state_changes = [UnitStateChange(unit=symbol, old_state=state, new_state=new_state)]
    return build_transaction(view, moves, state_changes)


def mark_to_market(
    view: LedgerView, symbol: str, price: float, settle_date: date | None = None
) -> PendingTransaction:
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
        return empty_pending_transaction(view)  # Idempotent

    mult, currency, ch_id = state['multiplier'], state['currency'], state['clearinghouse']
    positions = view.get_positions(symbol)
    wallet_states = dict(state.get('wallets', {}))
    moves = []

    # Settle all wallets that have either a position or virtual_cash
    wallet_ids_to_settle = set(positions.keys()) | set(wallet_states.keys())

    for wallet_id in sorted(wallet_ids_to_settle):
        ledger_position = positions.get(wallet_id, 0.0)
        wallet_state = wallet_states.get(wallet_id, {})
        vcash = wallet_state.get('virtual_cash', 0.0)
        state_position = wallet_state.get('position', 0.0)

        # Validate position consistency (defense-in-depth)
        if wallet_id in wallet_states and abs(state_position - ledger_position) >= QUANTITY_EPSILON:
            raise ValueError(f"Position mismatch for {wallet_id}: state={state_position}, ledger={ledger_position}")

        # Skip if nothing to settle
        if abs(ledger_position) < QUANTITY_EPSILON and abs(vcash) < QUANTITY_EPSILON:
            continue

        target_vcash = -ledger_position * price * mult
        vm = vcash - target_vcash

        # Skip move creation for clearinghouse: Move requires src != dest,
        # and CH settlement is already reflected in the bilateral moves with traders
        if abs(vm) > QUANTITY_EPSILON and wallet_id != ch_id:
            src, dst, q = (ch_id, wallet_id, vm) if vm > 0 else (wallet_id, ch_id, -vm)
            moves.append(Move(
                quantity=q, unit_symbol=currency, source=src, dest=dst,
                contract_id=f'mtm_{symbol}_{wallet_id}',
                metadata={'note': f'MTM {symbol} at {price}'}
            ))

        # Reset or remove wallet state
        if abs(ledger_position) < QUANTITY_EPSILON:
            # Position is zero, clear the wallet state entirely
            wallet_states.pop(wallet_id, None)
        else:
            wallet_states[wallet_id] = {'position': ledger_position, 'virtual_cash': target_vcash}

    new_state = {**state, 'wallets': wallet_states, 'last_settle_price': price, 'last_settle_date': settle_date}
    state_changes = [UnitStateChange(unit=symbol, old_state=state, new_state=new_state)]
    return build_transaction(view, moves, state_changes)


def future_contract(
    view: LedgerView, symbol: str, timestamp: datetime, prices: Dict[str, float]
) -> PendingTransaction:
    """SmartContract: daily MTM and expiry. Called by LifecycleEngine."""
    state = view.get_unit_state(symbol)
    if state.get('settled'):
        return empty_pending_transaction(view)
    price = prices.get(state.get('underlying'))
    if price is None:
        return empty_pending_transaction(view)

    result = mark_to_market(view, symbol, price, settle_date=timestamp.date())

    if state.get('expiry') and timestamp >= state['expiry']:
        # Find the state delta for this symbol, fallback to original state
        mtm_state = next(
            (d.new_state for d in result.state_changes if d.unit == symbol),
            state
        )
        updated = {**mtm_state, 'settled': True, 'settlement_price': price}
        state_changes = [UnitStateChange(unit=symbol, old_state=state, new_state=updated)]
        return build_transaction(view, list(result.moves), state_changes)
    return result
