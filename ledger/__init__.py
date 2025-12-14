"""
ledger - Financial Ledger System

A modular ledger implementation for financial simulations and portfolio tracking.

Usage:
    from ledger import Ledger, cash, Move, build_transaction, SYSTEM_WALLET

    ledger = Ledger("main")
    ledger.register_unit(cash("USD", "US Dollar"))
    ledger.register_wallet("alice")
    ledger.register_wallet("bob")
    ledger.register_wallet(SYSTEM_WALLET)

    # Fund wallets via SYSTEM_WALLET (proper issuance)
    funding = build_transaction(ledger, [
        Move(1000.0, "USD", SYSTEM_WALLET, "alice", "initial_balance")
    ])
    ledger.execute(funding)

    # Transfer between wallets
    tx = build_transaction(ledger, [
        Move(100.0, "USD", "alice", "bob", "payment_001")
    ])
    result = ledger.execute(tx)
"""

# Core types
from .core import (
    LedgerView,
    SmartContract,
    Move,
    Transaction,
    PendingTransaction,
    TransactionOrigin,
    OriginType,
    build_transaction,
    empty_pending_transaction,
    Unit,
    UnitStateChange,
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
    UNIT_TYPE_FUTURE,
    UNIT_TYPE_AUTOCALLABLE,
    UNIT_TYPE_MARGIN_LOAN,
    UNIT_TYPE_PORTFOLIO_SWAP,
    UNIT_TYPE_STRUCTURED_NOTE,
    UNIT_TYPE_BORROW_RECORD,
    UNIT_TYPE_LOCATE,
    UNIT_TYPE_QIS,
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
    Dividend,
    SplitAdjustment,
    BorrowSplitAdjustment,
    create_stock_unit,
    process_dividends,
    compute_stock_split,
    compute_split_adjustments,
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
    Coupon,
    CouponEntitlement,
    create_bond_unit,
    compute_accrued_interest,
    compute_coupon_entitlements,
    process_coupons,
    compute_redemption,
    transact as bond_transact,
    bond_contract,
    year_fraction,
)

# Futures
from .units.future import (
    create_future,
    mark_to_market as future_mark_to_market,
    future_contract,
    transact as future_transact,
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
    # Frozen dataclasses (pure function architecture)
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

# Borrow Records (SBL)
from .units.borrow_record import (
    create_borrow_record_unit,
    initiate_borrow,
    compute_borrow_return,
    initiate_recall,
    compute_available_position,
    compute_borrow_fee,
    compute_required_collateral,
    validate_short_sale,
    get_active_borrows,
    get_total_borrowed,
    borrow_record_contract,
    BorrowStatus,
    ContractType as BorrowContractType,
)

# Lifecycle
from .lifecycle_engine import LifecycleEngine

# Scheduled Events (simplified API)
from .scheduled_events import (
    Event,
    EventScheduler,
    EventHandler,
    dividend_event,
    coupon_event,
    maturity_event,
    expiry_event,
    settlement_event,
    split_event,
)

from .event_handlers import (
    handle_dividend,
    handle_coupon,
    handle_maturity,
    handle_expiry,
    handle_settlement,
    handle_split,
    DEFAULT_HANDLERS,
    create_default_scheduler,
)

# Pricing sources
from .pricing_source import (
    PricingSource,
    StaticPricingSource,
    TimeSeriesPricingSource,
)

# QIS (Quantitative Investment Strategy)
from .units.qis import (
    create_qis,
    compute_nav as compute_qis_nav,
    accrue_financing as accrue_qis_financing,
    compute_rebalance as compute_qis_rebalance,
    compute_payoff as compute_qis_payoff,
    compute_qis_settlement,
    qis_contract,
    leveraged_strategy,
    fixed_weight_strategy,
    get_qis_nav,
    get_qis_return,
    get_qis_leverage,
    Strategy as QISStrategy,
)

__all__ = [
    # Core
    'LedgerView', 'Move', 'Transaction', 'PendingTransaction', 'TransactionOrigin', 'OriginType',
    'build_transaction', 'empty_pending_transaction',
    'Unit', 'UnitStateChange',
    'ExecuteResult', 'LedgerError', 'InsufficientFunds', 'BalanceConstraintViolation',
    'TransferRuleViolation', 'UnitNotRegistered', 'WalletNotRegistered',
    'bilateral_transfer_rule', 'cash',
    'SYSTEM_WALLET',
    'UNIT_TYPE_CASH', 'UNIT_TYPE_STOCK', 'UNIT_TYPE_BILATERAL_OPTION',
    'UNIT_TYPE_BILATERAL_FORWARD', 'UNIT_TYPE_DEFERRED_CASH', 'UNIT_TYPE_DELTA_HEDGE_STRATEGY',
    'UNIT_TYPE_BOND', 'UNIT_TYPE_FUTURE', 'UNIT_TYPE_AUTOCALLABLE', 'UNIT_TYPE_MARGIN_LOAN',
    'UNIT_TYPE_PORTFOLIO_SWAP', 'UNIT_TYPE_BORROW_RECORD', 'UNIT_TYPE_LOCATE',
    # Ledger
    'Ledger',
    # Black-Scholes
    'call', 'put', 'call_delta', 'put_delta', 'call_gamma', 'put_gamma',
    'call_vega', 'put_vega', 'call_theta', 'put_theta', 'call_impvol', 'put_impvol',
    'gamma', 'vega',
    # Options
    'create_option_unit', 'compute_option_settlement',
    'compute_option_exercise', 'get_option_intrinsic_value', 'get_option_moneyness',
    'option_contract', 'option_transact',
    # Forwards
    'create_forward_unit', 'compute_forward_settlement', 'compute_early_termination',
    'get_forward_value', 'forward_contract', 'forward_transact',
    # Delta hedge
    'create_delta_hedge_unit', 'compute_rebalance', 'compute_liquidation',
    'get_hedge_state', 'compute_hedge_pnl_breakdown', 'delta_hedge_contract',
    # Stocks
    'Dividend', 'SplitAdjustment', 'BorrowSplitAdjustment',
    'create_stock_unit', 'process_dividends', 'compute_stock_split',
    'compute_split_adjustments', 'stock_contract', 'stock_transact',
    # DeferredCash
    'create_deferred_cash_unit', 'compute_deferred_cash_settlement',
    'deferred_cash_transact', 'deferred_cash_contract',
    # Bonds
    'Coupon', 'CouponEntitlement',
    'create_bond_unit', 'compute_accrued_interest', 'compute_coupon_entitlements',
    'process_coupons', 'compute_redemption', 'bond_transact', 'bond_contract',
    'year_fraction',
    # Futures
    'create_future', 'future_mark_to_market', 'future_contract', 'future_transact',
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
    # Borrow Records (SBL)
    'create_borrow_record_unit', 'initiate_borrow', 'compute_borrow_return',
    'initiate_recall', 'compute_available_position', 'compute_borrow_fee',
    'compute_required_collateral', 'validate_short_sale', 'get_active_borrows',
    'get_total_borrowed', 'borrow_record_contract', 'BorrowStatus', 'BorrowContractType',
    # Lifecycle
    'SmartContract', 'LifecycleEngine',
    # Scheduled Events (simplified)
    'Event', 'EventScheduler', 'EventHandler',
    'dividend_event', 'coupon_event', 'maturity_event',
    'expiry_event', 'settlement_event', 'split_event',
    # Event Handlers
    'handle_dividend', 'handle_coupon', 'handle_maturity',
    'handle_expiry', 'handle_settlement', 'handle_split',
    'DEFAULT_HANDLERS', 'create_default_scheduler',
    # Pricing
    'PricingSource', 'StaticPricingSource', 'TimeSeriesPricingSource',
    # QIS
    'UNIT_TYPE_QIS', 'create_qis', 'compute_qis_nav', 'accrue_qis_financing',
    'compute_qis_rebalance', 'compute_qis_payoff', 'compute_qis_settlement',
    'qis_contract', 'leveraged_strategy', 'fixed_weight_strategy',
    'get_qis_nav', 'get_qis_return', 'get_qis_leverage', 'QISStrategy',
]

__version__ = '4.0.0'
