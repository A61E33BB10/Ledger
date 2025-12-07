"""
options.py - Pure Functions for Option Creation and Settlement

This module provides functions for creating and managing bilateral option contracts
with physical delivery. All functions take LedgerView (read-only) and return
immutable results.
"""

from __future__ import annotations
from datetime import datetime
import math
from typing import Dict, Any, List

from ..core import (
    LedgerView, Move, ContractResult, Unit,
    bilateral_transfer_rule,
    UNIT_TYPE_BILATERAL_OPTION,
)


def create_option_unit(
    symbol: str,
    name: str,
    underlying: str,
    strike: float,
    maturity: datetime,
    option_type: str,
    quantity: float,
    currency: str,
    long_wallet: str,
    short_wallet: str,
) -> Unit:
    """
    Create a bilateral option unit with physical delivery.

    Args:
        symbol: Unique identifier (e.g., "AAPL_CALL_150_DEC25")
        name: Human-readable name
        underlying: Asset to be delivered (e.g., "AAPL")
        strike: Price per unit of underlying
        maturity: Expiration datetime
        option_type: "call" or "put"
        quantity: Number of underlying units per contract
        currency: Currency for premium and strike payment
        long_wallet: Long party (pays premium, has right)
        short_wallet: Short party (receives premium, has obligation)

    Returns:
        Unit configured with bilateral transfer rule.
    """
    if option_type not in ("call", "put"):
        raise ValueError(f"option_type must be 'call' or 'put', got {option_type}")
    if strike <= 0:
        raise ValueError(f"strike must be positive, got {strike}")
    if quantity <= 0:
        raise ValueError(f"quantity must be positive, got {quantity}")

    return Unit(
        symbol=symbol,
        name=name,
        unit_type=UNIT_TYPE_BILATERAL_OPTION,
        min_balance=-10_000.0,
        max_balance=10_000.0,
        decimal_places=2,
        transfer_rule=bilateral_transfer_rule,
        _state={
            'underlying': underlying,
            'strike': strike,
            'maturity': maturity,
            'option_type': option_type,
            'quantity': quantity,
            'currency': currency,
            'long_wallet': long_wallet,
            'short_wallet': short_wallet,
            'settled': False,
            'settlement_price': None,
            'exercised': False,
        }
    )


def build_option_trade(
    option_symbol: str,
    num_contracts: float,
    premium_per_contract: float,
    buyer: str,
    seller: str,
    premium_currency: str,
    trade_id: str,
) -> ContractResult:
    """
    Build moves for an option trade (premium payment + option transfer).

    Args:
        option_symbol: Symbol of the option to trade
        num_contracts: Number of option contracts
        premium_per_contract: Premium amount per contract
        buyer: Wallet address of the buyer (long party)
        seller: Wallet address of the seller (short party)
        premium_currency: Currency for premium payment
        trade_id: Unique identifier for this trade

    Returns:
        ContractResult containing moves for premium payment and option transfer.
    """
    total_premium = num_contracts * premium_per_contract

    moves = [
        Move(
            source=buyer,
            dest=seller,
            unit=premium_currency,
            quantity=total_premium,
            contract_id=f"{trade_id}_premium",
        ),
        Move(
            source=seller,
            dest=buyer,
            unit=option_symbol,
            quantity=num_contracts,
            contract_id=f"{trade_id}_option",
        ),
    ]

    return ContractResult(moves=tuple(moves))


def compute_option_settlement(
    view: LedgerView,
    option_symbol: str,
    settlement_price: float,
    force_settlement: bool = False,
) -> ContractResult:
    """
    Compute physical delivery settlement for a bilateral option.

    Args:
        view: Read-only ledger view
        option_symbol: Symbol of the option to settle
        settlement_price: Market price of the underlying at settlement
        force_settlement: If True, settle before maturity

    Returns:
        ContractResult containing settlement moves and state updates.

    Settlement logic:
        CALL (ITM when settlement_price > strike):
            - Long pays strike × quantity to short
            - Short delivers underlying to long

        PUT (ITM when settlement_price < strike):
            - Long delivers underlying to short
            - Short pays strike × quantity to long

        OTM: Option expires worthless, positions just close out.

    The function only settles if the option has reached maturity (or force_settlement
    is True) and has not already been settled.
    """
    if not (settlement_price > 0 and math.isfinite(settlement_price)):
        raise ValueError(f"settlement_price must be positive and finite, got {settlement_price}")

    state = view.get_unit_state(option_symbol)

    if state.get('settled'):
        return ContractResult()

    maturity = state['maturity']
    if view.current_time < maturity and not force_settlement:
        return ContractResult()

    long_wallet = state['long_wallet']
    short_wallet = state['short_wallet']
    long_position = view.get_balance(long_wallet, option_symbol)

    if long_position <= 0:
        return ContractResult()

    strike = state['strike']
    quantity = state['quantity']
    option_type = state['option_type']
    currency = state['currency']
    underlying = state['underlying']

    is_itm = (settlement_price > strike) if option_type == 'call' else (settlement_price < strike)

    moves: List[Move] = []

    if is_itm:
        underlying_amount = long_position * quantity
        cash_amount = underlying_amount * strike

        if option_type == 'call':
            moves.append(Move(
                source=long_wallet,
                dest=short_wallet,
                unit=currency,
                quantity=cash_amount,
                contract_id=f'settle_{option_symbol}_cash',
            ))
            moves.append(Move(
                source=short_wallet,
                dest=long_wallet,
                unit=underlying,
                quantity=underlying_amount,
                contract_id=f'settle_{option_symbol}_delivery',
            ))
        else:
            moves.append(Move(
                source=long_wallet,
                dest=short_wallet,
                unit=underlying,
                quantity=underlying_amount,
                contract_id=f'settle_{option_symbol}_delivery',
            ))
            moves.append(Move(
                source=short_wallet,
                dest=long_wallet,
                unit=currency,
                quantity=cash_amount,
                contract_id=f'settle_{option_symbol}_cash',
            ))

    # Close out option positions
    moves.append(Move(
        source=long_wallet,
        dest=short_wallet,
        unit=option_symbol,
        quantity=long_position,
        contract_id=f'close_{option_symbol}',
    ))

    # Mark option as settled in unit state
    state_updates = {
        option_symbol: {
            **state,
            'settled': True,
            'settlement_price': settlement_price,
            'exercised': is_itm,
        }
    }

    return ContractResult(moves=tuple(moves), state_updates=state_updates)


def get_option_intrinsic_value(
    view: LedgerView,
    option_symbol: str,
    spot_price: float,
) -> float:
    """
    Calculate intrinsic value of an option per contract.

    Args:
        view: Read-only ledger view
        option_symbol: Symbol of the option
        spot_price: Current market price of the underlying

    Returns:
        Intrinsic value in currency units per contract.
        For calls: max(0, spot_price - strike) × quantity
        For puts: max(0, strike - spot_price) × quantity
    """
    state = view.get_unit_state(option_symbol)
    strike = state['strike']
    quantity = state['quantity']
    option_type = state['option_type']

    if option_type == 'call':
        intrinsic = max(0, spot_price - strike)
    else:
        intrinsic = max(0, strike - spot_price)

    return intrinsic * quantity


def get_option_moneyness(
    view: LedgerView,
    option_symbol: str,
    spot_price: float,
) -> str:
    """
    Get moneyness status of an option.

    Args:
        view: Read-only ledger view
        option_symbol: Symbol of the option
        spot_price: Current market price of the underlying

    Returns:
        'ITM' (in-the-money), 'ATM' (at-the-money), or 'OTM' (out-of-the-money)

    ATM is determined using a tolerance of 1% of the strike price.
    """
    state = view.get_unit_state(option_symbol)
    strike = state['strike']
    option_type = state['option_type']

    # ATM tolerance: within 1% of strike
    atm_tolerance = strike * 0.01

    if abs(spot_price - strike) <= atm_tolerance:
        return 'ATM'

    if option_type == 'call':
        return 'ITM' if spot_price > strike else 'OTM'
    else:  # put
        return 'ITM' if spot_price < strike else 'OTM'


def compute_option_exercise(
    view: LedgerView,
    option_symbol: str,
    settlement_price: float,
) -> ContractResult:
    """
    Compute early exercise of an option (before maturity).

    Args:
        view: Read-only ledger view
        option_symbol: Symbol of the option to exercise
        settlement_price: Current market price of the underlying

    Returns:
        ContractResult with exercise settlement moves and state updates.
    """
    return compute_option_settlement(view, option_symbol, settlement_price, force_settlement=True)


def transact(
    view: LedgerView,
    symbol: str,
    event_type: str,
    event_date: datetime,
    **kwargs
) -> ContractResult:
    """
    Generate moves and state updates for an option lifecycle event.

    This is the unified entry point for all option lifecycle events, routing
    to the appropriate handler based on event_type.

    Args:
        view: Read-only ledger access
        symbol: Option symbol
        event_type: Type of event (EXERCISE, EXPIRY, ASSIGNMENT)
        event_date: When the event occurs
        **kwargs: Event-specific parameters:
            - For EXERCISE: settlement_price (float, required)
            - For EXPIRY: settlement_price (float, required)
            - For ASSIGNMENT: settlement_price (float, required)

    Returns:
        ContractResult with moves and state_updates, or empty result
        if event_type is unknown.

    Example:
        # Exercise an option early
        result = transact(ledger, "AAPL_CALL_150", "EXERCISE",
                         datetime(2024, 6, 1), settlement_price=155.0)

        # Expire an option at maturity
        result = transact(ledger, "AAPL_CALL_150", "EXPIRY",
                         datetime(2024, 12, 20), settlement_price=160.0)
    """
    settlement_price = kwargs.get('settlement_price')

    if settlement_price is None:
        # Cannot process option events without a settlement price
        return ContractResult()

    handlers = {
        'EXERCISE': lambda: compute_option_exercise(view, symbol, settlement_price),
        'EXPIRY': lambda: compute_option_settlement(view, symbol, settlement_price, force_settlement=False),
        'ASSIGNMENT': lambda: compute_option_settlement(view, symbol, settlement_price, force_settlement=True),
    }

    handler = handlers.get(event_type)
    if handler is None:
        return ContractResult()  # Unknown event type - no action

    return handler()


def option_contract(
    view: LedgerView,
    symbol: str,
    timestamp: datetime,
    prices: Dict[str, float]
) -> ContractResult:
    """
    SmartContract function for bilateral options.

    This function is called by the LifecycleEngine to automatically settle options
    at maturity. It checks if the option has reached maturity and settles it using
    the provided market prices.

    Args:
        view: Read-only ledger view
        symbol: Option symbol
        timestamp: Current timestamp
        prices: Dictionary mapping asset symbols to their current prices

    Returns:
        ContractResult with settlement moves if conditions are met, empty otherwise.
    """
    state = view.get_unit_state(symbol)

    if state.get('settled'):
        return ContractResult()

    maturity = state.get('maturity')
    if not maturity or timestamp < maturity:
        return ContractResult()

    underlying = state.get('underlying')
    settlement_price = prices.get(underlying)
    if settlement_price is None:
        return ContractResult()

    return compute_option_settlement(view, symbol, settlement_price)
