"""
forwards.py - Pure Functions for Forward Contract Creation and Settlement

This module provides functions for creating and settling bilateral forward contracts.
All functions are pure: they take LedgerView (read-only) and return immutable results.
"""

from __future__ import annotations
import math
from datetime import datetime
from typing import Dict, Any, List

from ..core import (
    LedgerView, Move, PendingTransaction, Unit, UnitStateChange,
    bilateral_transfer_rule,
    TransferRuleViolation,
    UNIT_TYPE_BILATERAL_FORWARD,
    build_transaction, empty_pending_transaction,
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
) -> PendingTransaction:
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
        PendingTransaction: Contains moves for cash payment, asset delivery, and position
        closure, plus state updates marking the contract as settled. Returns empty
        result if already settled, delivery date not reached, or long position is zero.
    """
    state = view.get_unit_state(forward_symbol)

    if state.get('settled'):
        return empty_pending_transaction(view)

    delivery_date = state['delivery_date']
    if view.current_time < delivery_date and not force_settlement:
        return empty_pending_transaction(view)

    long_wallet = state['long_wallet']
    short_wallet = state['short_wallet']
    long_position = view.get_balance(long_wallet, forward_symbol)

    if long_position <= 0:
        return empty_pending_transaction(view)

    quantity = state['quantity']
    forward_price = state['forward_price']
    currency = state['currency']
    underlying = state['underlying']

    total_underlying = long_position * quantity
    total_cash = total_underlying * forward_price

    moves = [
        Move(
            quantity=total_cash,
            unit_symbol=currency,
            source=long_wallet,
            dest=short_wallet,
            contract_id=f'settle_{forward_symbol}_cash',
        ),
        Move(
            quantity=total_underlying,
            unit_symbol=underlying,
            source=short_wallet,
            dest=long_wallet,
            contract_id=f'settle_{forward_symbol}_delivery',
        ),
        Move(
            quantity=long_position,
            unit_symbol=forward_symbol,
            source=long_wallet,
            dest=short_wallet,
            contract_id=f'close_{forward_symbol}',
        ),
    ]

    new_state = {
        **state,
        'settled': True,
    }
    state_changes = [UnitStateChange(unit=forward_symbol, old_state=state, new_state=new_state)]

    return build_transaction(view, moves, state_changes)


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
) -> PendingTransaction:
    """
    Compute early termination of a forward contract (before delivery date).

    Args:
        view: Read-only view of the ledger state
        forward_symbol: Symbol of the forward contract to terminate

    Returns:
        PendingTransaction with early settlement moves and state updates.
    """
    return compute_forward_settlement(view, forward_symbol, force_settlement=True)


def transact(
    view: LedgerView,
    symbol: str,
    seller: str,
    buyer: str,
    qty: float,
    price: float,
) -> PendingTransaction:
    """
    Execute a secondary market trade (novation/assignment) for forward contracts.

    In forward markets, secondary trading involves novation or assignment where
    the forward contract position is transferred from the seller to the buyer.
    The price represents the mark-to-market value or assignment fee.

    Args:
        view: Read-only view of the ledger state
        symbol: Symbol of the forward contract to trade
        seller: Wallet address of the seller (current position holder)
        buyer: Wallet address of the buyer (new position holder)
        qty: Number of forward contracts to transfer (must be positive)
        price: Mark-to-market value or assignment fee per contract
               Positive = buyer pays seller
               Negative = seller pays buyer

    Returns:
        PendingTransaction with two moves:
            1. Forward contract transfer: seller → buyer (qty contracts)
            2. Cash transfer: direction depends on price sign

    Raises:
        ValueError: If qty <= 0, seller == buyer, forward is settled,
                   or price is not finite
        TransferRuleViolation: If seller or buyer is not authorized to trade
                              the forward contract

    Example:
        # Buyer pays seller 100 for 5 forward contracts
        result = transact(view, "OIL_FWD_MAR25", "alice", "bob", 5.0, 100.0)

        # Seller pays buyer 50 (negative price) for 3 forward contracts
        result = transact(view, "OIL_FWD_MAR25", "alice", "bob", 3.0, -50.0)
    """
    # Validation
    if qty <= 0:
        raise ValueError(f"qty must be positive, got {qty}")

    if seller == buyer:
        raise ValueError(f"seller and buyer must be different, got {seller}")

    if not math.isfinite(price):
        raise ValueError(f"price must be finite, got {price}")

    # Get forward contract state
    state = view.get_unit_state(symbol)

    # Check if already settled
    if state.get('settled'):
        raise ValueError(f"Forward contract {symbol} is already settled")

    # Transfer rule validation: check if seller and buyer are authorized
    long_wallet = state.get('long_wallet')
    short_wallet = state.get('short_wallet')

    if not long_wallet or not short_wallet:
        raise TransferRuleViolation(
            f"Bilateral unit {symbol} missing counterparty state"
        )

    # Build set of authorized wallets (includes novation source if present)
    novation_from = state.get('_novation_from')
    authorized = {long_wallet, short_wallet}
    if novation_from:
        authorized.add(novation_from)

    # Check if seller and buyer are authorized
    if seller not in authorized:
        raise TransferRuleViolation(
            f"Bilateral {symbol}: seller {seller} not authorized"
        )
    if buyer not in authorized:
        raise TransferRuleViolation(
            f"Bilateral {symbol}: buyer {buyer} not authorized"
        )

    # Get currency from state for cash transfer
    currency = state['currency']

    # Create moves
    moves = [
        # Transfer forward contracts from seller to buyer
        Move(
            quantity=qty,
            unit_symbol=symbol,
            source=seller,
            dest=buyer,
            contract_id=f'forward_trade_{symbol}_contract',
        )
    ]

    # Add cash move based on price sign
    total_value = qty * abs(price)
    if price > 0:
        # Buyer pays seller
        moves.append(
            Move(
                quantity=total_value,
                unit_symbol=currency,
                source=buyer,
                dest=seller,
                contract_id=f'forward_trade_{symbol}_value',
            )
        )
    elif price < 0:
        # Seller pays buyer
        moves.append(
            Move(
                quantity=total_value,
                unit_symbol=currency,
                source=seller,
                dest=buyer,
                contract_id=f'forward_trade_{symbol}_value',
            )
        )
    # If price == 0, no cash transfer needed

    return build_transaction(view, moves)


def forward_contract(
    view: LedgerView,
    symbol: str,
    timestamp: datetime,
    prices: Dict[str, float]
) -> PendingTransaction:
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
        PendingTransaction: Settlement moves and state updates if delivery date reached,
        otherwise empty result.
    """
    state = view.get_unit_state(symbol)

    if state.get('settled'):
        return empty_pending_transaction(view)

    delivery_date = state.get('delivery_date')
    if not delivery_date or timestamp < delivery_date:
        return empty_pending_transaction(view)

    return compute_forward_settlement(view, symbol)
