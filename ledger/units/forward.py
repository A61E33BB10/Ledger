"""
forwards.py - Pure Functions for Forward Contract Creation and Settlement

This module provides functions for creating and settling bilateral forward contracts.
All functions are pure: they take LedgerView (read-only) and return immutable results.
"""

from __future__ import annotations
from datetime import datetime
from typing import Dict, Any, List

from ..core import (
    LedgerView, Move, ContractResult, Unit,
    bilateral_transfer_rule,
    UNIT_TYPE_BILATERAL_FORWARD,
)


def create_forward_unit(
    symbol: str,
    name: str,
    underlying: str,
    forward_price: float,
    delivery_date: datetime,
    quantity: float,
    currency: str,
    long_wallet: str,
    short_wallet: str,
) -> Unit:
    """
    Create a bilateral forward contract unit.

    A forward contract is an agreement between two parties to exchange an underlying
    asset for a predetermined price at a future delivery date. The long party agrees
    to buy and the short party agrees to sell.

    Args:
        symbol: Unique identifier for the forward contract (e.g., "OIL_FWD_MAR25")
        name: Human-readable name for the contract
        underlying: Symbol of the asset to be delivered (e.g., "OIL")
        forward_price: Agreed price per unit of the underlying asset
        delivery_date: Date and time when settlement occurs
        quantity: Number of underlying units per forward contract
        currency: Symbol of the currency used for payment
        long_wallet: Wallet address of the buying party
        short_wallet: Wallet address of the selling party

    Returns:
        Unit: A forward contract unit with type "BILATERAL_FORWARD" and bilateral
        transfer rule. Contract state is stored in the unit's _state dictionary.

    Raises:
        ValueError: If forward_price or quantity is not positive.
    """
    if forward_price <= 0:
        raise ValueError(f"forward_price must be positive, got {forward_price}")
    if quantity <= 0:
        raise ValueError(f"quantity must be positive, got {quantity}")

    return Unit(
        symbol=symbol,
        name=name,
        unit_type=UNIT_TYPE_BILATERAL_FORWARD,
        min_balance=-10_000.0,
        max_balance=10_000.0,
        decimal_places=2,
        transfer_rule=bilateral_transfer_rule,
        _state={
            'underlying': underlying,
            'forward_price': forward_price,
            'delivery_date': delivery_date,
            'quantity': quantity,
            'currency': currency,
            'long_wallet': long_wallet,
            'short_wallet': short_wallet,
            'settled': False,
        }
    )


def compute_forward_settlement(
    view: LedgerView,
    forward_symbol: str,
    force_settlement: bool = False,
) -> ContractResult:
    """
    Compute physical delivery settlement for a bilateral forward contract.

    Settlement occurs when the delivery date is reached (or earlier if forced).
    The function returns moves that execute the following steps:
        1. Long party pays (forward_price × quantity × long_position) in currency to short party
        2. Short party delivers (quantity × long_position) units of underlying to long party
        3. Forward contract position is closed (long position transferred back to short)

    Args:
        view: Read-only view of the ledger state
        forward_symbol: Symbol of the forward contract to settle
        force_settlement: If True, settle even before delivery_date. Defaults to False.

    Returns:
        ContractResult: Contains moves for cash payment, asset delivery, and position
        closure, plus state updates marking the contract as settled. Returns empty
        result if already settled, delivery date not reached, or long position is zero.
    """
    state = view.get_unit_state(forward_symbol)

    if state.get('settled'):
        return ContractResult()

    delivery_date = state['delivery_date']
    if view.current_time < delivery_date and not force_settlement:
        return ContractResult()

    long_wallet = state['long_wallet']
    short_wallet = state['short_wallet']
    long_position = view.get_balance(long_wallet, forward_symbol)

    if long_position <= 0:
        return ContractResult()

    quantity = state['quantity']
    forward_price = state['forward_price']
    currency = state['currency']
    underlying = state['underlying']

    total_underlying = long_position * quantity
    total_cash = total_underlying * forward_price

    moves = [
        Move(
            source=long_wallet,
            dest=short_wallet,
            unit=currency,
            quantity=total_cash,
            contract_id=f'settle_{forward_symbol}_cash',
        ),
        Move(
            source=short_wallet,
            dest=long_wallet,
            unit=underlying,
            quantity=total_underlying,
            contract_id=f'settle_{forward_symbol}_delivery',
        ),
        Move(
            source=long_wallet,
            dest=short_wallet,
            unit=forward_symbol,
            quantity=long_position,
            contract_id=f'close_{forward_symbol}',
        ),
    ]

    state_updates = {
        forward_symbol: {
            **state,
            'settled': True,
        }
    }

    return ContractResult(moves=tuple(moves), state_updates=state_updates)


def get_forward_value(
    view: LedgerView,
    forward_symbol: str,
    spot_price: float,
) -> float:
    """
    Calculate the current mark-to-market value of one forward contract to the long party.

    The value represents the profit or loss if the forward were settled at the current
    spot price instead of the agreed forward price.

    Args:
        view: Read-only view of the ledger state
        forward_symbol: Symbol of the forward contract
        spot_price: Current market price of the underlying asset

    Returns:
        float: Value per forward contract calculated as (spot_price - forward_price) × quantity.
        Positive values indicate profit for the long party, negative values indicate loss.
    """
    state = view.get_unit_state(forward_symbol)
    forward_price = state['forward_price']
    quantity = state['quantity']
    return (spot_price - forward_price) * quantity


def compute_early_termination(
    view: LedgerView,
    forward_symbol: str,
) -> ContractResult:
    """
    Compute early termination of a forward contract (before delivery date).

    Args:
        view: Read-only view of the ledger state
        forward_symbol: Symbol of the forward contract to terminate

    Returns:
        ContractResult with early settlement moves and state updates.
    """
    return compute_forward_settlement(view, forward_symbol, force_settlement=True)


def transact(
    view: LedgerView,
    symbol: str,
    event_type: str,
    event_date: datetime,
    **kwargs
) -> ContractResult:
    """
    Generate moves and state updates for a forward contract lifecycle event.

    This is the unified entry point for all forward contract lifecycle events,
    routing to the appropriate handler based on event_type.

    Args:
        view: Read-only ledger access
        symbol: Forward contract symbol
        event_type: Type of event (DELIVERY, EARLY_TERMINATION)
        event_date: When the event occurs
        **kwargs: Event-specific parameters (currently none required)

    Returns:
        ContractResult with moves and state_updates, or empty result
        if event_type is unknown.

    Example:
        # Process delivery at maturity
        result = transact(ledger, "OIL_FWD_MAR25", "DELIVERY", datetime(2025, 3, 15))

        # Process early termination
        result = transact(ledger, "OIL_FWD_MAR25", "EARLY_TERMINATION", datetime(2025, 2, 1))
    """
    handlers = {
        'DELIVERY': lambda: compute_forward_settlement(view, symbol, force_settlement=False),
        'EARLY_TERMINATION': lambda: compute_early_termination(view, symbol),
    }

    handler = handlers.get(event_type)
    if handler is None:
        return ContractResult()  # Unknown event type - no action

    return handler()


def forward_contract(
    view: LedgerView,
    symbol: str,
    timestamp: datetime,
    prices: Dict[str, float]
) -> ContractResult:
    """
    SmartContract function for automatic settlement of bilateral forward contracts.

    This function is called by the lifecycle engine to automatically settle forward
    contracts when the delivery date is reached. It checks if settlement is due and
    delegates to compute_forward_settlement if appropriate.

    Args:
        view: Read-only view of the ledger state
        symbol: Symbol of the forward contract unit
        timestamp: Current simulation time
        prices: Market prices (not used for forward settlement)

    Returns:
        ContractResult: Settlement moves and state updates if delivery date reached,
        otherwise empty result.
    """
    state = view.get_unit_state(symbol)

    if state.get('settled'):
        return ContractResult()

    delivery_date = state.get('delivery_date')
    if not delivery_date or timestamp < delivery_date:
        return ContractResult()

    return compute_forward_settlement(view, symbol)
