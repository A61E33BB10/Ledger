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

from ..core import (
    LedgerView, Move, ContractResult, Unit,
    SYSTEM_WALLET, UNIT_TYPE_DEFERRED_CASH, QUANTITY_EPSILON,
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
) -> ContractResult:
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
        ContractResult containing:
        - Cash move from payer to payee
        - Extinguish move (payee → system)
        - State update marking as settled

        Returns empty ContractResult if:
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
        ledger.execute_contract(result)
        # Result contains:
        # - Move(payer, payee, currency, amount)
        # - Move(payee, system, dc_symbol, 1)
    """
    state = view.get_unit_state(dc_symbol)

    # Check if already settled
    if state.get('settled', False):
        return ContractResult()

    # Check if payment date reached
    payment_date = state['payment_date']
    if settlement_time < payment_date:
        return ContractResult()

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
        return ContractResult()

    # Generate settlement moves
    moves = [
        # Cash payment from payer to payee
        Move(
            source=payer_wallet,
            dest=payee_wallet,
            unit=currency,
            quantity=amount,
            contract_id=f'settlement_{dc_symbol}_cash',
        ),
        # Extinguish the obligation/entitlement (holder returns to system)
        Move(
            source=holder,
            dest=SYSTEM_WALLET,
            unit=dc_symbol,
            quantity=holder_balance,
            contract_id=f'settlement_{dc_symbol}_extinguish',
        ),
    ]

    # Mark as settled in unit state
    state_updates = {
        dc_symbol: {
            **state,
            'settled': True,
            'settlement_time': settlement_time,
        }
    }

    return ContractResult(moves=tuple(moves), state_updates=state_updates)


def transact(
    view: LedgerView,
    symbol: str,
    event_type: str,
    event_date: datetime,
    **kwargs
) -> ContractResult:
    """
    Generate moves and state updates for a DeferredCash lifecycle event.

    Args:
        view: Read-only ledger access
        symbol: DeferredCash unit symbol
        event_type: Type of event (currently only 'SETTLEMENT' is supported)
        event_date: When the event occurs
        **kwargs: Event-specific parameters (unused for SETTLEMENT)

    Returns:
        ContractResult with moves and state_updates

    Supported event types:
        SETTLEMENT: Execute the deferred cash payment on payment_date

    Example:
        # Manual settlement trigger
        result = transact(
            ledger,
            "DC_trade_123",
            "SETTLEMENT",
            datetime(2024, 3, 17)
        )
        ledger.execute_contract(result)
    """
    if event_type == 'SETTLEMENT':
        return compute_deferred_cash_settlement(view, symbol, event_date)
    else:
        raise ValueError(f"Unknown event_type for DeferredCash: {event_type}")


def deferred_cash_contract(
    view: LedgerView,
    symbol: str,
    timestamp: datetime,
    prices: Dict[str, float]
) -> ContractResult:
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
        ContractResult with settlement moves if payment is due,
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
        return ContractResult()

    # Check if payment date reached
    payment_date = state.get('payment_date')
    if not payment_date or timestamp < payment_date:
        return ContractResult()

    return compute_deferred_cash_settlement(view, symbol, timestamp)
