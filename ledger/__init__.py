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
    SYSTEM_WALLET,
    UNIT_TYPE_CASH,
    UNIT_TYPE_STOCK,
    UNIT_TYPE_BILATERAL_OPTION,
    UNIT_TYPE_BILATERAL_FORWARD,
    UNIT_TYPE_DEFERRED_CASH,
    UNIT_TYPE_DELTA_HEDGE_STRATEGY,
    UNIT_TYPE_BOND,
    UNIT_TYPE_AUTOCALLABLE,
    UNIT_TYPE_MARGIN_LOAN,
    UNIT_TYPE_PORTFOLIO_SWAP,
    UNIT_TYPE_STRUCTURED_NOTE,
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
from .units.option import (
    create_option_unit,
    build_option_trade,
    compute_option_settlement,
    compute_option_exercise,
    get_option_intrinsic_value,
    get_option_moneyness,
    option_contract,
    transact as option_transact,
)

# Forwards
from .units.forward import (
    create_forward_unit,
    compute_forward_settlement,
    compute_early_termination,
    get_forward_value,
    forward_contract,
    transact as forward_transact,
)

# Delta hedge
from .strategies.delta_hedge import (
    create_delta_hedge_unit,
    compute_rebalance,
    compute_liquidation,
    get_hedge_state,
    compute_hedge_pnl_breakdown,
    delta_hedge_contract,
)

# Stocks
from .units.stock import (
    create_stock_unit,
    compute_scheduled_dividend,
    compute_stock_split,
    stock_contract,
    transact as stock_transact,
)

# DeferredCash
from .units.deferred_cash import (
    create_deferred_cash_unit,
    compute_deferred_cash_settlement,
    transact as deferred_cash_transact,
    deferred_cash_contract,
)

# Bonds
from .units.bond import (
    create_bond_unit,
    compute_accrued_interest,
    compute_coupon_payment,
    compute_redemption,
    transact as bond_transact,
    bond_contract,
    generate_coupon_schedule,
    year_fraction,
)

# Futures
from .units.future import (
    create_future_unit,
    execute_futures_trade,
    compute_daily_settlement,
    compute_intraday_margin,
    compute_expiry,
    future_contract,
    transact as future_transact,
    UNIT_TYPE_FUTURE,
)

# Autocallables
from .units.autocallable import (
    create_autocallable,
    compute_observation,
    compute_maturity_payoff,
    autocallable_contract,
    transact as autocallable_transact,
    get_autocallable_status,
    get_total_coupons_paid,
)

# Margin Loans
from .units.margin_loan import (
    # Frozen dataclasses (new pure function architecture)
    MarginLoanTerms,
    MarginLoanState,
    MarginStatusResult,
    # Adapter functions
    load_margin_loan,
    to_state_dict,
    # Pure calculation functions (no LedgerView, all inputs explicit)
    calculate_collateral_value,
    calculate_pending_interest,
    calculate_total_debt,
    calculate_margin_status,
    calculate_interest_accrual,
    # Convenience functions (load + calculate)
    create_margin_loan,
    compute_collateral_value,
    compute_margin_status,
    compute_interest_accrual,
    compute_margin_call,
    compute_margin_cure,
    compute_liquidation as compute_margin_loan_liquidation,
    compute_repayment,
    compute_add_collateral,
    transact as margin_loan_transact,
    margin_loan_contract,
    MARGIN_STATUS_HEALTHY,
    MARGIN_STATUS_WARNING,
    MARGIN_STATUS_BREACH,
    MARGIN_STATUS_LIQUIDATION,
)

# Portfolio Swaps
from .units.portfolio_swap import (
    create_portfolio_swap,
    compute_portfolio_nav,
    compute_funding_amount,
    compute_swap_reset,
    compute_termination as compute_swap_termination,
    transact as portfolio_swap_transact,
    portfolio_swap_contract,
)

# Structured Notes
from .units.structured_note import (
    create_structured_note,
    compute_performance,
    compute_payoff_rate,
    compute_coupon_payment as compute_structured_note_coupon,
    compute_maturity_payoff as compute_structured_note_maturity,
    structured_note_contract,
    transact as structured_note_transact,
    generate_structured_note_coupon_schedule,
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
    'SYSTEM_WALLET',
    'UNIT_TYPE_CASH', 'UNIT_TYPE_STOCK', 'UNIT_TYPE_BILATERAL_OPTION',
    'UNIT_TYPE_BILATERAL_FORWARD', 'UNIT_TYPE_DEFERRED_CASH', 'UNIT_TYPE_DELTA_HEDGE_STRATEGY',
    'UNIT_TYPE_BOND', 'UNIT_TYPE_FUTURE', 'UNIT_TYPE_AUTOCALLABLE', 'UNIT_TYPE_MARGIN_LOAN',
    'UNIT_TYPE_PORTFOLIO_SWAP',
    # Ledger
    'Ledger',
    # Black-Scholes
    'call', 'put', 'call_delta', 'put_delta', 'call_gamma', 'put_gamma',
    'call_vega', 'put_vega', 'call_theta', 'put_theta', 'call_impvol', 'put_impvol',
    'gamma', 'vega',
    # Options
    'create_option_unit', 'build_option_trade', 'compute_option_settlement',
    'compute_option_exercise', 'get_option_intrinsic_value', 'get_option_moneyness',
    'option_contract', 'option_transact',
    # Forwards
    'create_forward_unit', 'compute_forward_settlement', 'compute_early_termination',
    'get_forward_value', 'forward_contract', 'forward_transact',
    # Delta hedge
    'create_delta_hedge_unit', 'compute_rebalance', 'compute_liquidation',
    'get_hedge_state', 'compute_hedge_pnl_breakdown', 'delta_hedge_contract',
    # Stocks
    'create_stock_unit', 'compute_scheduled_dividend', 'compute_stock_split',
    'stock_contract', 'stock_transact',
    # DeferredCash
    'create_deferred_cash_unit', 'compute_deferred_cash_settlement',
    'deferred_cash_transact', 'deferred_cash_contract',
    # Bonds
    'create_bond_unit', 'compute_accrued_interest', 'compute_coupon_payment',
    'compute_redemption', 'bond_transact', 'bond_contract',
    'generate_coupon_schedule', 'year_fraction',
    # Futures
    'create_future_unit', 'execute_futures_trade', 'compute_daily_settlement',
    'compute_intraday_margin', 'compute_expiry', 'future_contract', 'future_transact',
    # Autocallables
    'create_autocallable', 'compute_observation', 'compute_maturity_payoff',
    'autocallable_contract', 'autocallable_transact',
    'get_autocallable_status', 'get_total_coupons_paid',
    # Margin Loans - Pure Function Architecture
    'MarginLoanTerms', 'MarginLoanState', 'MarginStatusResult',
    'load_margin_loan', 'to_state_dict',
    'calculate_collateral_value', 'calculate_pending_interest',
    'calculate_total_debt', 'calculate_margin_status', 'calculate_interest_accrual',
    'create_margin_loan', 'compute_collateral_value', 'compute_margin_status',
    'compute_interest_accrual', 'compute_margin_call', 'compute_margin_cure',
    'compute_margin_loan_liquidation', 'compute_repayment', 'compute_add_collateral',
    'margin_loan_transact', 'margin_loan_contract',
    'MARGIN_STATUS_HEALTHY', 'MARGIN_STATUS_WARNING', 'MARGIN_STATUS_BREACH',
    'MARGIN_STATUS_LIQUIDATION',
    # Portfolio Swaps
    'create_portfolio_swap', 'compute_portfolio_nav', 'compute_funding_amount',
    'compute_swap_reset', 'compute_swap_termination', 'portfolio_swap_transact',
    'portfolio_swap_contract',
    # Structured Notes
    'create_structured_note', 'compute_performance', 'compute_payoff_rate',
    'compute_structured_note_coupon', 'compute_structured_note_maturity',
    'structured_note_contract', 'structured_note_transact',
    'generate_structured_note_coupon_schedule', 'UNIT_TYPE_STRUCTURED_NOTE',
    # Lifecycle
    'SmartContract', 'LifecycleEngine',
    # Pricing
    'PricingSource', 'StaticPricingSource', 'TimeSeriesPricingSource',
]

__version__ = '1.0.0'
