"""
deferred_cash.py - DeferredCash Unit for T+n Settlement

This module provides DeferredCash unit creation and settlement processing:
1. create_deferred_cash_unit() - Factory for DeferredCash units representing payment obligations
2. compute_deferred_cash_settlement() - Pure function for payment execution
3. transact() - Event-driven interface for SETTLEMENT events
4. deferred_cash_contract() - SmartContract for LifecycleEngine integration

DeferredCash represents future payment obligations (e.g., T+2 stock settlement, dividend payments).
It's a first-class Unit that tracks who owes what to whom, with a payment date.

Pattern:
    Trade Date (T):
        - Stock moves immediately
        - Create DeferredCash obligation (settles T+2)
        Move(source="system", dest="buyer", unit="DC_trade_123", quantity=1)

    Settlement Date (T+2):
        - Cash payment fires
        Move(source="buyer", dest="seller", unit="USD", quantity=15000)
        - Extinguish the obligation
        Move(source="buyer", dest="system", unit="DC_trade_123", quantity=1)

All functions take LedgerView (read-only) and return immutable results.
"""

from __future__ import annotations
from datetime import datetime
from typing import Dict, Any

import math

from ..core import (
    LedgerView, Move, PendingTransaction, Unit, UnitStateChange,
    SYSTEM_WALLET, UNIT_TYPE_DEFERRED_CASH, QUANTITY_EPSILON,
    build_transaction, empty_pending_transaction,
)


def create_deferred_cash_unit(
    symbol: str,
    amount: float,
    currency: str,
    payment_date: datetime,
    payer_wallet: str,
    payee_wallet: str,
    reference: str = None,
) -> Unit:
    """
    Create a DeferredCash unit representing a future payment obligation.

    Args:
        symbol: Unique identifier (e.g., "DC_trade_123", "DIV_AAPL_2024-03-15_alice")
        amount: Payment amount in the specified currency
        currency: Currency symbol for the payment (e.g., "USD")
        payment_date: When the payment should execute
        payer_wallet: Wallet that will make the payment
        payee_wallet: Wallet that will receive the payment
        reference: Optional reference to trade/dividend/other source

    Returns:
        Unit configured for DeferredCash with quantity always 1.
        The unit stores payment state including:
        - amount: payment amount
        - currency: payment currency
        - payment_date: when payment executes
        - payer_wallet: who pays
        - payee_wallet: who receives
        - settled: whether payment has been executed
        - reference: optional reference ID

    Example:
        # Trade settlement obligation
        dc_unit = create_deferred_cash_unit(
            symbol="DC_trade_123",
            amount=15000.0,
            currency="USD",
            payment_date=datetime(2024, 3, 17),  # T+2
            payer_wallet="buyer",
            payee_wallet="seller",
            reference="trade_123"
        )
        ledger.register_unit(dc_unit)
        # Create the obligation
        ledger.move("system", "buyer", "DC_trade_123", 1, "trade_settlement_obligation")
    """
    if amount <= 0:
        raise ValueError(f"amount must be positive, got {amount}")
    if not currency or not currency.strip():
        raise ValueError("currency cannot be empty")
    if not payer_wallet or not payer_wallet.strip():
        raise ValueError("payer_wallet cannot be empty")
    if not payee_wallet or not payee_wallet.strip():
        raise ValueError("payee_wallet cannot be empty")
    if payer_wallet == payee_wallet:
        raise ValueError("payer_wallet and payee_wallet must be different")

    return Unit(
        symbol=symbol,
        name=f"Deferred Cash Payment: {amount} {currency}",
        unit_type=UNIT_TYPE_DEFERRED_CASH,
        min_balance=-1.0,  # Allow slight negative for system extinguishment
        max_balance=1.0,   # Quantity is always 1
        decimal_places=0,  # No fractional DeferredCash units
        transfer_rule=None,
        _state={
            'amount': amount,
            'currency': currency,
            'payment_date': payment_date,
            'payer_wallet': payer_wallet,
            'payee_wallet': payee_wallet,
            'settled': False,
            'reference': reference,
        }
    )


def compute_deferred_cash_settlement(
    view: LedgerView,
    dc_symbol: str,
    settlement_time: datetime,
) -> PendingTransaction:
    """
    Execute deferred cash payment if due.

    This function checks if the DeferredCash payment date has been reached.
    If so, it generates:
    1. Cash move from payer to payee
    2. Extinguish move (payee → system) to close the obligation

    Args:
        view: Read-only ledger access
        dc_symbol: Symbol of the DeferredCash unit
        settlement_time: Current timestamp to check against payment_date

    Returns:
        PendingTransaction containing:
        - Cash move from payer to payee
        - Extinguish move (payee → system)
        - State update marking as settled

        Returns empty PendingTransaction if:
        - Payment date not yet reached
        - Already settled
        - Payee has no DeferredCash position (already extinguished)

    Example:
        # On settlement date (T+2)
        result = compute_deferred_cash_settlement(
            ledger,
            "DC_trade_123",
            datetime(2024, 3, 17)
        )
        ledger.execute(result)
        # Result contains:
        # - Move(payer, payee, currency, amount)
        # - Move(payee, system, dc_symbol, 1)
    """
    state = view.get_unit_state(dc_symbol)

    # Check if already settled
    if state.get('settled', False):
        return empty_pending_transaction(view)

    # Check if payment date reached
    payment_date = state['payment_date']
    if settlement_time < payment_date:
        return empty_pending_transaction(view)

    # Get payment details
    amount = state['amount']
    currency = state['currency']
    payer_wallet = state['payer_wallet']
    payee_wallet = state['payee_wallet']

    # Check who holds the DeferredCash unit
    # It could be either the payer (trade settlement) or payee (dividend entitlement)
    payer_balance = view.get_balance(payer_wallet, dc_symbol)
    payee_balance = view.get_balance(payee_wallet, dc_symbol)

    if payer_balance > QUANTITY_EPSILON:
        # Payer holds the obligation (trade settlement pattern)
        holder = payer_wallet
        holder_balance = payer_balance
    elif payee_balance > QUANTITY_EPSILON:
        # Payee holds the entitlement (dividend pattern)
        holder = payee_wallet
        holder_balance = payee_balance
    else:
        # Nobody holds it - already settled or invalid state
        return empty_pending_transaction(view)

    # Generate settlement moves
    moves = [
        # Cash payment from payer to payee
        Move(
            quantity=amount,
            unit_symbol=currency,
            source=payer_wallet,
            dest=payee_wallet,
            contract_id=f'settlement_{dc_symbol}_cash',
        ),
        # Extinguish the obligation/entitlement (holder returns to system)
        Move(
            quantity=holder_balance,
            unit_symbol=dc_symbol,
            source=holder,
            dest=SYSTEM_WALLET,
            contract_id=f'settlement_{dc_symbol}_extinguish',
        ),
    ]

    # Mark as settled in unit state
    new_state = {
        **state,
        'settled': True,
        'settlement_time': settlement_time,
    }
    state_changes = [UnitStateChange(unit=dc_symbol, old_state=state, new_state=new_state)]

    return build_transaction(view, moves, state_changes)


def transact(
    view: LedgerView,
    symbol: str,
    seller: str,
    buyer: str,
    qty: float,
    price: float,
) -> PendingTransaction:
    """
    Execute a DeferredCash unit trade (assignment of the payment obligation).

    This enables secondary market trading of deferred payment obligations.
    The buyer acquires the right to receive (or obligation to pay) based on
    whether they're buying the payee or payer position.

    Args:
        view: Read-only ledger access.
        symbol: DeferredCash unit symbol.
        seller: Wallet selling the DeferredCash unit.
        buyer: Wallet buying the DeferredCash unit.
        qty: Quantity to transfer (positive, typically 1 for DeferredCash).
        price: Assignment price per unit (present value of the obligation).

    Returns:
        PendingTransaction containing:
        - Move transferring the DeferredCash unit from seller to buyer.
        - Move transferring cash from buyer to seller (if price > 0).

    Raises:
        ValueError: If qty <= 0, price < 0, seller == buyer, or invalid state.

    Example:
        # Alice assigns her T+2 settlement right to Bob for $14,900
        result = transact(
            view, "DC_trade_123",
            seller_id="alice",
            buyer_id="bob",
            qty=1,
            price=14900.0  # Slight discount to face value
        )
        ledger.execute(result)
    """
    # Validate quantity
    if qty <= 0:
        raise ValueError(f"qty must be positive, got {qty}")

    # Validate price
    if not math.isfinite(price) or price < 0:
        raise ValueError(f"price must be non-negative and finite, got {price}")

    # Validate wallets
    if seller == buyer:
        raise ValueError("seller and buyer must be different")

    # Get unit state
    state = view.get_unit_state(symbol)

    # Check if already settled
    if state.get('settled', False):
        raise ValueError(f"DeferredCash {symbol} has already been settled")

    # Check seller has sufficient balance
    seller_balance = view.get_balance(seller, symbol)
    if seller_balance < qty - QUANTITY_EPSILON:
        raise ValueError(
            f"Seller {seller} has insufficient balance: {seller_balance} < {qty}"
        )

    currency = state['currency']

    # Build moves
    moves = [
        # Transfer the DeferredCash unit
        Move(
            quantity=qty,
            unit_symbol=symbol,
            source=seller,
            dest=buyer,
            contract_id=f'dc_trade_{symbol}_unit',
        ),
    ]

    # Cash payment if price > 0
    total_payment = qty * price
    if total_payment > QUANTITY_EPSILON:
        moves.append(Move(
            quantity=total_payment,
            unit_symbol=currency,
            source=buyer,
            dest=seller,
            contract_id=f'dc_trade_{symbol}_cash',
        ))

    return build_transaction(view, moves)


def deferred_cash_contract(
    view: LedgerView,
    symbol: str,
    timestamp: datetime,
    prices: Dict[str, float]
) -> PendingTransaction:
    """
    SmartContract interface for DeferredCash with LifecycleEngine.

    This function provides the SmartContract interface required by LifecycleEngine.
    It automatically settles DeferredCash obligations when their payment date is reached.

    Args:
        view: Read-only ledger access
        symbol: DeferredCash symbol to process
        timestamp: Current time for payment date checking
        prices: Price data (unused for DeferredCash settlement)

    Returns:
        PendingTransaction with settlement moves if payment is due,
        or empty result if not yet due or already settled.

    Example:
        # Register with LifecycleEngine
        engine = LifecycleEngine(ledger)
        engine.register("DEFERRED_CASH", deferred_cash_contract)

        # Engine will automatically settle on payment dates
        timestamps = [datetime(2024, 3, i) for i in range(15, 20)]
        engine.run(timestamps, lambda ts: {})
    """
    state = view.get_unit_state(symbol)

    # Check if already settled
    if state.get('settled', False):
        return empty_pending_transaction(view)

    # Check if payment date reached
    payment_date = state.get('payment_date')
    if not payment_date or timestamp < payment_date:
        return empty_pending_transaction(view)

    return compute_deferred_cash_settlement(view, symbol, timestamp)
