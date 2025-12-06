"""
stocks.py - Stock Contracts with Dividend Scheduling

This module provides stock unit creation and dividend processing:
1. create_stock_unit() - Factory for stock units with dividend schedule
2. compute_scheduled_dividend() - Pure function for dividend payments
3. stock_contract - SmartContract for LifecycleEngine integration

Dividend schedules are represented as lists of (payment_date, dividend_per_share) tuples.
All functions take LedgerView (read-only) and return immutable results.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

from .core import (
    LedgerView, Move, ContractResult, Unit,
    STOCK_DECIMAL_PLACES, DEFAULT_STOCK_SHORT_MIN_BALANCE,
)


# Type alias for dividend schedule
DividendSchedule = List[Tuple[datetime, float]]


def create_stock_unit(
    symbol: str,
    name: str,
    issuer: str,
    currency: str,
    dividend_schedule: DividendSchedule = None,
    shortable: bool = False,
) -> Unit:
    """
    Create a stock unit with an optional dividend schedule.

    Args:
        symbol: Unique stock identifier (e.g., "AAPL")
        name: Human-readable stock name (e.g., "Apple Inc.")
        issuer: Wallet that issues shares and pays dividends
        currency: Currency symbol for dividend payments
        dividend_schedule: Optional list of (payment_date, dividend_per_share) tuples.
                          If None, stock has no scheduled dividends.
        shortable: If True, allows negative balances (short selling) with
                  min_balance set to DEFAULT_STOCK_SHORT_MIN_BALANCE.
                  If False, min_balance is 0.

    Returns:
        Unit configured for stock trading with dividend lifecycle support.
        The unit stores dividend state including:
        - issuer: wallet paying dividends
        - currency: payment currency
        - shortable: short selling flag
        - dividend_schedule: payment schedule
        - next_payment_index: tracks which dividend to pay next
        - paid_dividends: history of completed payments

    Example:
        schedule = [
            (datetime(2024, 3, 15), 0.25),
            (datetime(2024, 6, 15), 0.25),
            (datetime(2024, 9, 15), 0.25),
            (datetime(2024, 12, 15), 0.25),
        ]
        unit = create_stock_unit("AAPL", "Apple Inc.", "treasury", "USD", schedule)
        ledger.register_unit(unit)
    """
    schedule = dividend_schedule or []
    min_balance = DEFAULT_STOCK_SHORT_MIN_BALANCE if shortable else 0.0

    return Unit(
        symbol=symbol,
        name=name,
        unit_type="STOCK",
        min_balance=min_balance,
        max_balance=float('inf'),
        decimal_places=STOCK_DECIMAL_PLACES,
        transfer_rule=None,
        _state={
            'issuer': issuer,
            'currency': currency,
            'shortable': shortable,
            'dividend_schedule': schedule,
            'next_payment_index': 0,
            'paid_dividends': [],
        }
    )


def compute_scheduled_dividend(
    view: LedgerView,
    stock_symbol: str,
    current_time: datetime,
) -> ContractResult:
    """
    Compute dividend payment if one is scheduled and due at current_time.

    This function checks if the next scheduled dividend payment has reached its
    payment_date. If so, it generates payment moves for all shareholders and
    updates the unit state to track the payment.

    Payment logic:
    - Only wallets with positive share balances receive dividends
    - The issuer wallet does not pay itself dividends
    - Payment amount = shares * dividend_per_share
    - Payments are sorted by wallet name for deterministic ordering

    Args:
        view: Read-only ledger access
        stock_symbol: Symbol of the stock unit
        current_time: Current timestamp to check against payment_date

    Returns:
        ContractResult containing:
        - moves: Tuple of Move objects transferring currency from issuer to shareholders
        - state_updates: Updates next_payment_index and appends to paid_dividends history
        Returns empty ContractResult if no dividend is due or schedule is exhausted.
    """
    state = view.get_unit_state(stock_symbol)
    schedule = state.get('dividend_schedule', [])
    next_idx = state.get('next_payment_index', 0)

    if next_idx >= len(schedule):
        return ContractResult()

    payment_date, dividend_per_share = schedule[next_idx]

    if current_time < payment_date:
        return ContractResult()

    issuer = state['issuer']
    currency = state['currency']
    positions = view.get_positions(stock_symbol)

    moves: List[Move] = []
    total_paid = 0.0

    for wallet in sorted(positions.keys()):
        shares = positions[wallet]
        if shares > 0 and wallet != issuer:
            payout = shares * dividend_per_share
            moves.append(Move(
                source=issuer,
                dest=wallet,
                unit=currency,
                quantity=payout,
                contract_id=f'dividend_{stock_symbol}_{next_idx}_{wallet}',
            ))
            total_paid += payout

    paid_dividends = list(state.get('paid_dividends', []))
    paid_dividends.append({
        'payment_number': next_idx,
        'payment_date': payment_date,
        'dividend_per_share': dividend_per_share,
        'total_paid': total_paid,
    })

    state_updates = {
        stock_symbol: {
            'issuer': issuer,
            'currency': currency,
            'shortable': state.get('shortable', False),
            'dividend_schedule': schedule,
            'next_payment_index': next_idx + 1,
            'paid_dividends': paid_dividends,
        }
    }

    return ContractResult(moves=tuple(moves), state_updates=state_updates)


def stock_contract(
    view: LedgerView,
    symbol: str,
    timestamp: datetime,
    prices: Dict[str, float]
) -> ContractResult:
    """
    SmartContract function for automatic dividend processing.

    This function provides the SmartContract interface required by LifecycleEngine.
    It delegates to compute_scheduled_dividend to handle dividend payments.

    Args:
        view: Read-only ledger access
        symbol: Stock symbol to process
        timestamp: Current time for dividend date checking
        prices: Price data (unused for dividend processing)

    Returns:
        ContractResult with dividend payment moves and state updates,
        or empty result if no dividend is due.
    """
    state = view.get_unit_state(symbol)
    schedule = state.get('dividend_schedule', [])
    next_idx = state.get('next_payment_index', 0)

    if next_idx >= len(schedule):
        return ContractResult()

    return compute_scheduled_dividend(view, symbol, timestamp)
