"""
ledger - Financial Ledger System

A modular ledger implementation for financial simulations and portfolio tracking.

Usage:
    from ledger import Ledger, cash, Move, create_stock_unit

    ledger = Ledger("main", fast_mode=True, no_log=True)
    ledger.register_unit(cash("USD", "US Dollar"))
    ledger.register_wallet("alice")
    ledger.register_wallet("bob")

    tx = ledger.create_transaction([
        Move("alice", "bob", "USD", 100.0, "payment_001")
    ])
    result = ledger.execute(tx)
"""

# Core types
from .core import (
    LedgerView,
    Move,
    Transaction,
    ContractResult,
    Unit,
    StateDelta,
    ExecuteResult,
    LedgerError,
    InsufficientFunds,
    BalanceConstraintViolation,
    TransferRuleViolation,
    UnitNotRegistered,
    WalletNotRegistered,
    bilateral_transfer_rule,
    cash,
)

# Ledger
from .ledger import Ledger

# Black-Scholes pricing and Greeks
from .black_scholes import (
    call, put,
    call_delta, put_delta,
    call_gamma, put_gamma,
    call_vega, put_vega,
    call_theta, put_theta,
    call_impvol, put_impvol,
    gamma, vega,
)

# Options
from .options import (
    create_option_unit,
    build_option_trade,
    compute_option_settlement,
    get_option_intrinsic_value,
    get_option_moneyness,
    option_contract,
)

# Forwards
from .forwards import (
    create_forward_unit,
    compute_forward_settlement,
    get_forward_value,
    forward_contract,
)

# Delta hedge
from .delta_hedge_strategy import (
    create_delta_hedge_unit,
    compute_rebalance,
    compute_liquidation,
    get_hedge_state,
    compute_hedge_pnl_breakdown,
    delta_hedge_contract,
)

# Stocks
from .stocks import (
    create_stock_unit,
    compute_scheduled_dividend,
    stock_contract,
)

# Lifecycle
from .lifecycle import (
    SmartContract,
    LifecycleEngine,
)

# Pricing sources
from .pricing_source import (
    PricingSource,
    StaticPricingSource,
    TimeSeriesPricingSource,
)

__all__ = [
    # Core
    'LedgerView', 'Move', 'Transaction', 'ContractResult', 'Unit', 'StateDelta',
    'ExecuteResult', 'LedgerError', 'InsufficientFunds', 'BalanceConstraintViolation',
    'TransferRuleViolation', 'UnitNotRegistered', 'WalletNotRegistered',
    'bilateral_transfer_rule', 'cash',
    # Ledger
    'Ledger',
    # Black-Scholes
    'call', 'put', 'call_delta', 'put_delta', 'call_gamma', 'put_gamma',
    'call_vega', 'put_vega', 'call_theta', 'put_theta', 'call_impvol', 'put_impvol',
    'gamma', 'vega',
    # Options
    'create_option_unit', 'build_option_trade', 'compute_option_settlement',
    'get_option_intrinsic_value', 'get_option_moneyness', 'option_contract',
    # Forwards
    'create_forward_unit', 'compute_forward_settlement', 'get_forward_value',
    'forward_contract',
    # Delta hedge
    'create_delta_hedge_unit', 'compute_rebalance', 'compute_liquidation',
    'get_hedge_state', 'compute_hedge_pnl_breakdown', 'delta_hedge_contract',
    # Stocks
    'create_stock_unit', 'compute_scheduled_dividend', 'stock_contract',
    # Lifecycle
    'SmartContract', 'LifecycleEngine',
    # Pricing
    'PricingSource', 'StaticPricingSource', 'TimeSeriesPricingSource',
]

__version__ = '1.0.0'
