"""
event_handlers.py - Event Handler Functions

Simple functions that process Event -> PendingTransaction.
Each handler delegates to existing pure functions in unit modules.

Following expert recommendations:
- No handler classes, just functions
- Dict of functions instead of class hierarchy
- Thin adapters between Event and unit module pure functions
"""

from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Dict

from .core import LedgerView, PendingTransaction, empty_pending_transaction
from .scheduled_events import Event, EventScheduler

# Import pure functions from unit modules
from .units.stock import process_dividends, compute_stock_split
from .units.bond import process_coupons, compute_redemption
from .units.option import compute_option_settlement
from .units.forward import compute_forward_settlement
from .units.deferred_cash import compute_deferred_cash_settlement


# ============================================================================
# HANDLER FUNCTIONS
# ============================================================================

def handle_dividend(
    event: Event,
    view: LedgerView,
    prices: Dict[str, Decimal],
) -> PendingTransaction:
    """Process dividend entitlement."""
    return process_dividends(
        view=view,
        symbol=event.symbol,
        timestamp=event.trigger_time,
    )


def handle_coupon(
    event: Event,
    view: LedgerView,
    prices: Dict[str, Decimal],
) -> PendingTransaction:
    """Process bond coupon payment."""
    return process_coupons(
        view=view,
        symbol=event.symbol,
        timestamp=event.trigger_time,
    )


def handle_maturity(
    event: Event,
    view: LedgerView,
    prices: Dict[str, Decimal],
) -> PendingTransaction:
    """Process bond maturity/redemption."""
    return compute_redemption(
        view=view,
        symbol=event.symbol,
        timestamp=event.trigger_time,
    )


def handle_expiry(
    event: Event,
    view: LedgerView,
    prices: Dict[str, Decimal],
) -> PendingTransaction:
    """Process option/derivative expiry."""
    params = event.params_dict
    underlying = params.get("underlying")
    if not underlying:
        raise ValueError(f"Missing 'underlying' in expiry event params for {event.symbol}")
    if underlying not in prices:
        raise ValueError(f"Missing price for underlying '{underlying}' in expiry settlement for {event.symbol}")
    settlement_price = prices[underlying]

    return compute_option_settlement(
        view=view,
        option_symbol=event.symbol,
        settlement_price=settlement_price,
    )


def handle_settlement(
    event: Event,
    view: LedgerView,
    prices: Dict[str, Decimal],
) -> PendingTransaction:
    """Process settlement (forward, cash, etc.)."""
    state = view.get_unit_state(event.symbol)
    unit_type = state.get("unit_type")
    if not unit_type:
        raise ValueError(f"Missing 'unit_type' in state for {event.symbol}")

    if unit_type == "FORWARD":
        underlying = state.get("underlying")
        if not underlying:
            raise ValueError(f"Missing 'underlying' in forward state for {event.symbol}")
        if underlying not in prices:
            raise ValueError(f"Missing price for underlying '{underlying}' in forward settlement for {event.symbol}")
        settlement_price = prices[underlying]
        return compute_forward_settlement(
            view=view,
            forward_symbol=event.symbol,
            settlement_price=settlement_price,
        )
    elif unit_type == "DEFERRED_CASH":
        return compute_deferred_cash_settlement(
            view=view,
            dc_symbol=event.symbol,
            settlement_time=event.trigger_time,
        )
    else:
        raise ValueError(f"Unknown unit_type '{unit_type}' in settlement event for {event.symbol}")


def handle_split(
    event: Event,
    view: LedgerView,
    prices: Dict[str, Decimal],
) -> PendingTransaction:
    """Process stock split."""
    params = event.params_dict
    ratio = params.get("ratio")
    if ratio is None:
        raise ValueError(f"Missing 'ratio' in split event params for {event.symbol}")
    ratio = Decimal(ratio)
    if ratio <= 0:
        raise ValueError(f"Split ratio must be positive, got {ratio} for {event.symbol}")

    return compute_stock_split(
        view=view,
        symbol=event.symbol,
        ratio=ratio,
        split_date=event.trigger_time,
    )


# ============================================================================
# HANDLER REGISTRY
# ============================================================================

# Map action strings to handler functions
DEFAULT_HANDLERS: Dict[str, callable] = {
    "dividend": handle_dividend,
    "coupon": handle_coupon,
    "maturity": handle_maturity,
    "expiry": handle_expiry,
    "settlement": handle_settlement,
    "split": handle_split,
}


def create_default_scheduler() -> EventScheduler:
    """
    Create an EventScheduler with all default handlers registered.
    """
    scheduler = EventScheduler()
    for action, handler in DEFAULT_HANDLERS.items():
        scheduler.register(action, handler)
    return scheduler
