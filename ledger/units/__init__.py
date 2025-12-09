"""
Units module - Factory functions for creating financial instruments.

This module provides factory functions for creating various types of units:
- Stock units with dividend schedules
- Option units (calls/puts) with physical delivery
- Forward contracts with bilateral settlement

All unit factories and related functions are re-exported here for convenience.
"""

# Stock units
from .stock import (
    create_stock_unit,
    compute_scheduled_dividend,
    compute_stock_split,
    stock_contract,
    transact as stock_transact,
)

# Option units
from .option import (
    create_option_unit,
    build_option_trade,
    compute_option_settlement,
    compute_option_exercise,
    get_option_intrinsic_value,
    get_option_moneyness,
    option_contract,
    transact as option_transact,
)

# Forward contracts
from .forward import (
    create_forward_unit,
    compute_forward_settlement,
    compute_early_termination,
    get_forward_value,
    forward_contract,
    transact as forward_transact,
)

# DeferredCash units
from .deferred_cash import (
    create_deferred_cash_unit,
    compute_deferred_cash_settlement,
    transact as deferred_cash_transact,
    deferred_cash_contract,
)

# Bond units
from .bond import (
    create_bond_unit,
    compute_accrued_interest,
    compute_coupon_payment,
    compute_redemption,
    transact as bond_transact,
    bond_contract,
    generate_coupon_schedule,
    year_fraction,
)

# Future contracts
from .future import (
    create_future,
    future_contract,
    transact as future_transact,
)

# Structured notes
from .structured_note import (
    create_structured_note,
    compute_performance,
    compute_payoff_rate,
    compute_coupon_payment as compute_structured_note_coupon,
    compute_maturity_payoff,
    structured_note_contract,
    transact as structured_note_transact,
    generate_structured_note_coupon_schedule,
)

__all__ = [
    # Stocks
    'create_stock_unit',
    'compute_scheduled_dividend',
    'compute_stock_split',
    'stock_contract',
    'stock_transact',
    # Options
    'create_option_unit',
    'build_option_trade',
    'compute_option_settlement',
    'compute_option_exercise',
    'get_option_intrinsic_value',
    'get_option_moneyness',
    'option_contract',
    'option_transact',
    # Forwards
    'create_forward_unit',
    'compute_forward_settlement',
    'compute_early_termination',
    'get_forward_value',
    'forward_contract',
    'forward_transact',
    # DeferredCash
    'create_deferred_cash_unit',
    'compute_deferred_cash_settlement',
    'deferred_cash_transact',
    'deferred_cash_contract',
    # Bonds
    'create_bond_unit',
    'compute_accrued_interest',
    'compute_coupon_payment',
    'compute_redemption',
    'bond_transact',
    'bond_contract',
    'generate_coupon_schedule',
    'year_fraction',
    # Futures
    'create_future',
    'future_contract',
    'future_transact',
    # Structured Notes
    'create_structured_note',
    'compute_performance',
    'compute_payoff_rate',
    'compute_structured_note_coupon',
    'compute_maturity_payoff',
    'structured_note_contract',
    'structured_note_transact',
    'generate_structured_note_coupon_schedule',
]
