"""
strategies - Trading strategy implementations for the Ledger system.

This module provides trading strategy implementations that operate on the ledger.
Each strategy is a pure function or callable that generates ContractResults.

Available strategies:
- delta_hedge: Delta hedging strategy for options using Black-Scholes
"""

from .delta_hedge import (
    create_delta_hedge_unit,
    compute_rebalance,
    compute_liquidation,
    get_hedge_state,
    compute_hedge_pnl_breakdown,
    delta_hedge_contract,
)

__all__ = [
    'create_delta_hedge_unit',
    'compute_rebalance',
    'compute_liquidation',
    'get_hedge_state',
    'compute_hedge_pnl_breakdown',
    'delta_hedge_contract',
]
