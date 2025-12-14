"""
options.py - Pure Functions for Option Creation and Settlement

This module provides functions for creating and managing bilateral option contracts
with physical delivery. All functions take LedgerView (read-only) and return
immutable results.
"""

from __future__ import annotations
from datetime import datetime
from decimal import Decimal
import math
from typing import Dict, Any, List

from ..core import (
    LedgerView, Move, PendingTransaction, Unit, UnitStateChange,
    bilateral_transfer_rule,
    TransferRuleViolation,
    UNIT_TYPE_BILATERAL_OPTION,
    build_transaction, empty_pending_transaction,
    _freeze_state,
)


def create_option_unit(
    symbol: str,
    name: str,
    underlying: str,
    strike: Decimal,
    maturity: datetime,
    option_type: str,
    quantity: Decimal,
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
    # Convert numeric parameters to Decimal to handle float inputs
    strike = Decimal(str(strike)) if not isinstance(strike, Decimal) else strike
    quantity = Decimal(str(quantity)) if not isinstance(quantity, Decimal) else quantity

    if option_type not in ("call", "put"):
        raise ValueError(f"option_type must be 'call' or 'put', got {option_type}")
    if strike <= Decimal("0"):
        raise ValueError(f"strike must be positive, got {strike}")
    if quantity <= Decimal("0"):
        raise ValueError(f"quantity must be positive, got {quantity}")

    return Unit(
        symbol=symbol,
        name=name,
        unit_type=UNIT_TYPE_BILATERAL_OPTION,
        min_balance=Decimal("-10000"),
        max_balance=Decimal("10000"),
        decimal_places=2,
        transfer_rule=bilateral_transfer_rule,
        _frozen_state=_freeze_state({
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
        })
    )


def compute_option_settlement(
    view: LedgerView,
    option_symbol: str,
    settlement_price: Decimal,
    force_settlement: bool = False,
) -> PendingTransaction:
    """
    Compute physical delivery settlement for a bilateral option.

    Args:
        view: Read-only ledger view
        option_symbol: Symbol of the option to settle
        settlement_price: Market price of the underlying at settlement
        force_settlement: If True, settle before maturity

    Returns:
        PendingTransaction containing settlement moves and state updates.

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
    # Convert settlement_price to Decimal to handle float inputs
    settlement_price = Decimal(str(settlement_price)) if not isinstance(settlement_price, Decimal) else settlement_price

    if not (settlement_price > Decimal("0") and settlement_price.is_finite()):
        raise ValueError(f"settlement_price must be positive and finite, got {settlement_price}")

    state = view.get_unit_state(option_symbol)

    if state.get('settled'):
        return empty_pending_transaction(view)

    maturity = state['maturity']
    if view.current_time < maturity and not force_settlement:
        return empty_pending_transaction(view)

    long_wallet = state['long_wallet']
    short_wallet = state['short_wallet']
    long_position = view.get_balance(long_wallet, option_symbol)

    if long_position <= Decimal("0"):
        return empty_pending_transaction(view)

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
                quantity=cash_amount,
                unit_symbol=currency,
                source=long_wallet,
                dest=short_wallet,
                contract_id=f'settle_{option_symbol}_cash',
            ))
            moves.append(Move(
                quantity=underlying_amount,
                unit_symbol=underlying,
                source=short_wallet,
                dest=long_wallet,
                contract_id=f'settle_{option_symbol}_delivery',
            ))
        else:
            moves.append(Move(
                quantity=underlying_amount,
                unit_symbol=underlying,
                source=long_wallet,
                dest=short_wallet,
                contract_id=f'settle_{option_symbol}_delivery',
            ))
            moves.append(Move(
                quantity=cash_amount,
                unit_symbol=currency,
                source=short_wallet,
                dest=long_wallet,
                contract_id=f'settle_{option_symbol}_cash',
            ))

    # Close out option positions
    moves.append(Move(
        quantity=long_position,
        unit_symbol=option_symbol,
        source=long_wallet,
        dest=short_wallet,
        contract_id=f'close_{option_symbol}',
    ))

    # Mark option as settled in unit state
    new_state = {
        **state,
        'settled': True,
        'settlement_price': settlement_price,
        'exercised': is_itm,
    }
    state_changes = [UnitStateChange(unit=option_symbol, old_state=state, new_state=new_state)]

    return build_transaction(view, moves, state_changes)


def get_option_intrinsic_value(
    view: LedgerView,
    option_symbol: str,
    spot_price: Decimal,
) -> Decimal:
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
    # Convert spot_price to Decimal to handle float inputs
    spot_price = Decimal(str(spot_price)) if not isinstance(spot_price, Decimal) else spot_price

    state = view.get_unit_state(option_symbol)
    strike = state['strike']
    quantity = state['quantity']
    option_type = state['option_type']

    if option_type == 'call':
        intrinsic = max(Decimal("0"), spot_price - strike)
    else:
        intrinsic = max(Decimal("0"), strike - spot_price)

    return intrinsic * quantity


def get_option_moneyness(
    view: LedgerView,
    option_symbol: str,
    spot_price: Decimal,
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
    # Convert spot_price to Decimal to handle float inputs
    spot_price = Decimal(str(spot_price)) if not isinstance(spot_price, Decimal) else spot_price

    state = view.get_unit_state(option_symbol)
    strike = state['strike']
    option_type = state['option_type']

    # ATM tolerance: within 1% of strike
    atm_tolerance = strike * Decimal("0.01")

    if abs(spot_price - strike) <= atm_tolerance:
        return 'ATM'

    if option_type == 'call':
        return 'ITM' if spot_price > strike else 'OTM'
    else:  # put
        return 'ITM' if spot_price < strike else 'OTM'


def compute_option_exercise(
    view: LedgerView,
    option_symbol: str,
    settlement_price: Decimal,
) -> PendingTransaction:
    """
    Compute early exercise of an option (before maturity).

    Args:
        view: Read-only ledger view
        option_symbol: Symbol of the option to exercise
        settlement_price: Current market price of the underlying

    Returns:
        PendingTransaction with exercise settlement moves and state updates.
    """
    # Convert settlement_price to Decimal to handle float inputs
    settlement_price = Decimal(str(settlement_price)) if not isinstance(settlement_price, Decimal) else settlement_price

    return compute_option_settlement(view, option_symbol, settlement_price, force_settlement=True)


def transact(
    view: LedgerView,
    symbol: str,
    seller: str,
    buyer: str,
    qty: Decimal,
    price: Decimal,
) -> PendingTransaction:
    """
    Transfer option contracts from seller to buyer with premium payment.

    This is the unified transaction interface for option trades. It creates
    direct transfers between the seller and buyer, with proper validation
    against the bilateral transfer rule.

    Args:
        view: Read-only ledger view
        symbol: Option symbol
        seller: Wallet address of the seller (transferring contracts)
        buyer: Wallet address of the buyer (receiving contracts)
        qty: Number of option contracts to transfer (must be positive)
        price: Premium per contract (must be non-negative)

    Returns:
        PendingTransaction containing moves for the option transfer and premium payment.

    Raises:
        ValueError: If qty <= 0, price < 0, price is not finite, seller == buyer,
                   or option is already settled
        TransferRuleViolation: If seller or buyer are not authorized counterparties

    Example:
        # Trade 5 option contracts at $2.50 premium per contract
        result = transact(view, "AAPL_CALL_150", "alice", "bob", 5.0, 2.50)
    """
    # Convert numeric parameters to Decimal to handle float inputs
    qty = Decimal(str(qty)) if not isinstance(qty, Decimal) else qty
    price = Decimal(str(price)) if not isinstance(price, Decimal) else price

    # Validate inputs
    if qty <= Decimal("0"):
        raise ValueError(f"qty must be positive, got {qty}")
    if price < Decimal("0"):
        raise ValueError(f"price must be non-negative, got {price}")
    if not price.is_finite():
        raise ValueError(f"price must be finite, got {price}")
    if seller == buyer:
        raise ValueError(f"seller and buyer must be different, got {seller}")

    # Get option state
    state = view.get_unit_state(symbol)

    # Check if option is settled
    if state.get('settled'):
        raise ValueError(f"Option {symbol} is already settled and cannot be traded")

    # Validate bilateral transfer rule
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
            f"Bilateral {symbol}: {seller} not authorized to trade"
        )
    if buyer not in authorized:
        raise TransferRuleViolation(
            f"Bilateral {symbol}: {buyer} not authorized to trade"
        )

    # Get currency from state
    currency = state.get('currency', 'USD')

    # Build moves
    moves: List[Move] = []

    # Move 1: Transfer option contracts from seller to buyer
    moves.append(Move(
        quantity=qty,
        unit_symbol=symbol,
        source=seller,
        dest=buyer,
        contract_id=f"option_trade_{symbol}_contract",
    ))

    # Move 2: Premium payment from buyer to seller (if price > 0)
    # Skip premium payment if price is effectively zero
    if price > Decimal("0"):
        total_premium = qty * price
        moves.append(Move(
            quantity=total_premium,
            unit_symbol=currency,
            source=buyer,
            dest=seller,
            contract_id=f"option_trade_{symbol}_premium",
        ))

    return build_transaction(view, moves)


def option_contract(
    view: LedgerView,
    symbol: str,
    timestamp: datetime,
    prices: Dict[str, Decimal]
) -> PendingTransaction:
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
        PendingTransaction with settlement moves if conditions are met, empty otherwise.
    """
    state = view.get_unit_state(symbol)

    if state.get('settled'):
        return empty_pending_transaction(view)

    maturity = state.get('maturity')
    if not maturity or timestamp < maturity:
        return empty_pending_transaction(view)

    underlying = state.get('underlying')
    if not underlying:
        raise ValueError(f"Option {symbol} has no underlying defined")
    if underlying not in prices:
        raise ValueError(f"Missing price for option underlying '{underlying}' in {symbol}")
    settlement_price = prices[underlying]

    # Convert settlement_price to Decimal to handle float inputs from prices dict
    settlement_price = Decimal(str(settlement_price)) if not isinstance(settlement_price, Decimal) else settlement_price

    return compute_option_settlement(view, symbol, settlement_price)
