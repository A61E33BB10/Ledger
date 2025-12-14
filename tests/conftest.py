"""
conftest.py - Shared pytest fixtures for Ledger tests

Provides common fixtures used across unit and functional tests:
- Basic ledgers (empty, funded, trading-ready)
- Instrument-specific ledgers (options, forwards, hedges)
- Lifecycle engine setups
- Comparison utilities
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, Set, Tuple, List, Any
from decimal import Decimal

from ledger import (
    # Core
    Ledger, Move, Transaction, Unit, UnitStateChange,
    ExecuteResult, LedgerView,
    cash,

    # Instruments
    create_stock_unit,
    create_option_unit,
    create_forward_unit,
    create_delta_hedge_unit,

    # Contracts
    stock_contract,
    option_contract,
    forward_contract,
    delta_hedge_contract,

    # Engine
    LifecycleEngine,

    # Pricing
    TimeSeriesPricingSource,

    # Dividends
    Dividend,
)

from tests.fake_view import FakeView


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_stock(symbol: str, name: str, issuer: str, shortable: bool = False, **kwargs) -> Unit:
    """Create a stock unit for testing."""
    return create_stock_unit(
        symbol=symbol,
        name=name,
        issuer=issuer,
        currency="USD",
        shortable=shortable,
        **kwargs
    )


def ledger_state_equals(ledger1: Ledger, ledger2: Ledger, tolerance: Decimal = None) -> bool:
    """Check if two ledgers have equivalent state (balances and unit states)."""
    if tolerance is None:
        tolerance = Decimal("1e-9")
    diff = compare_ledger_states(ledger1, ledger2, tolerance)
    return diff["equal"]


def compare_ledger_states(ledger1: Ledger, ledger2: Ledger, tolerance: Decimal = None) -> dict:
    """Compare two ledger states and return differences."""
    if tolerance is None:
        tolerance = Decimal("1e-9")
    balance_diffs = []
    state_diffs = []

    # Compare balances
    all_wallets = ledger1.registered_wallets | ledger2.registered_wallets
    all_units = set(ledger1.units.keys()) | set(ledger2.units.keys())

    for wallet in all_wallets:
        for unit in all_units:
            bal1 = ledger1.balances.get(wallet, {}).get(unit, Decimal("0"))
            bal2 = ledger2.balances.get(wallet, {}).get(unit, Decimal("0"))
            if abs(bal1 - bal2) > tolerance:
                balance_diffs.append({
                    "wallet": wallet,
                    "unit": unit,
                    "ledger1": bal1,
                    "ledger2": bal2,
                    "diff": bal1 - bal2
                })

    # Compare unit states
    for unit_sym in all_units:
        if unit_sym in ledger1.units and unit_sym in ledger2.units:
            state1 = ledger1.get_unit_state(unit_sym)
            state2 = ledger2.get_unit_state(unit_sym)

            # Compare each field
            all_keys = set(state1.keys()) | set(state2.keys())
            field_diffs = {}
            for key in all_keys:
                v1 = state1.get(key)
                v2 = state2.get(key)
                if isinstance(v1, float) and isinstance(v2, float):
                    if abs(v1 - v2) > tolerance:
                        field_diffs[key] = {"ledger1": v1, "ledger2": v2}
                elif v1 != v2:
                    field_diffs[key] = {"ledger1": v1, "ledger2": v2}

            if field_diffs:
                state_diffs.append({
                    "unit": unit_sym,
                    "diffs": field_diffs
                })

    return {
        "equal": len(balance_diffs) == 0 and len(state_diffs) == 0,
        "balance_diffs": balance_diffs,
        "state_diffs": state_diffs,
    }


def verify_conservation(ledger: Ledger, unit_symbol: str, expected_total: Decimal = None, tolerance: Decimal = None) -> Tuple[bool, Decimal]:
    """
    Verify conservation law for a unit.

    Returns:
        (is_conserved, actual_total)
    """
    if tolerance is None:
        tolerance = Decimal("1e-9")
    actual = ledger.total_supply(unit_symbol)
    if expected_total is not None:
        return abs(actual - expected_total) < tolerance, actual
    return True, actual


# =============================================================================
# BASIC FIXTURES
# =============================================================================

@pytest.fixture
def empty_ledger():
    """Fresh ledger with no registrations."""
    return Ledger("test", verbose=False, test_mode=True)


@pytest.fixture
def basic_ledger():
    """Ledger with USD and two wallets."""
    ledger = Ledger("test", datetime(2025, 1, 1), verbose=False, test_mode=True)
    ledger.register_unit(cash("USD", "US Dollar", decimal_places=2))
    ledger.register_wallet("alice")
    ledger.register_wallet("bob")
    return ledger


@pytest.fixture
def funded_ledger(basic_ledger):
    """Basic ledger with alice having $10,000."""
    basic_ledger.set_balance("alice", "USD", Decimal("10000"))
    return basic_ledger


# =============================================================================
# TRADING FIXTURES
# =============================================================================

@pytest.fixture
def trading_ledger():
    """Ledger ready for stock trading with multiple wallets."""
    ledger = Ledger("trading", datetime(2025, 1, 1), verbose=False, test_mode=True)
    ledger.register_unit(cash("USD", "US Dollar", decimal_places=2))
    ledger.register_unit(create_stock("AAPL", "Apple Inc", "treasury", shortable=True))

    # Register wallets
    ledger.register_wallet("alice")
    ledger.register_wallet("bob")
    ledger.register_wallet("treasury")
    ledger.register_wallet("market")

    # Fund wallets
    ledger.set_balance("alice", "USD", Decimal("100000"))
    ledger.set_balance("bob", "USD", Decimal("50000"))
    ledger.set_balance("treasury", "USD", Decimal("10000000"))
    ledger.set_balance("market", "USD", Decimal("1000000"))
    ledger.set_balance("market", "AAPL", Decimal("100000"))

    return ledger


@pytest.fixture
def multi_stock_ledger():
    """Ledger with multiple stocks for testing."""
    ledger = Ledger("multi_stock", datetime(2025, 1, 1), verbose=False, test_mode=True)
    ledger.register_unit(cash("USD", "US Dollar", decimal_places=2))
    ledger.register_unit(create_stock("AAPL", "Apple Inc", "treasury", shortable=True))
    ledger.register_unit(create_stock("MSFT", "Microsoft Corp", "treasury", shortable=True))
    ledger.register_unit(create_stock("GOOGL", "Alphabet Inc", "treasury", shortable=False))

    ledger.register_wallet("alice")
    ledger.register_wallet("bob")
    ledger.register_wallet("treasury")
    ledger.register_wallet("market")

    ledger.set_balance("alice", "USD", Decimal("1000000"))
    ledger.set_balance("market", "AAPL", Decimal("100000"))
    ledger.set_balance("market", "MSFT", Decimal("100000"))
    ledger.set_balance("market", "GOOGL", Decimal("100000"))
    ledger.set_balance("market", "USD", Decimal("10000000"))

    return ledger


# =============================================================================
# DIVIDEND FIXTURES
# =============================================================================

@pytest.fixture
def dividend_ledger():
    """Ledger with stock that has dividend schedule."""
    ledger = Ledger("dividend", datetime(2025, 1, 1), verbose=False, test_mode=True)
    ledger.register_unit(cash("USD", "US Dollar", decimal_places=2))

    # Stock with quarterly dividend schedule
    dividend_schedule = [
        Dividend(datetime(2025, 3, 15), datetime(2025, 3, 15), Decimal("0.25"), "USD"),
        Dividend(datetime(2025, 6, 15), datetime(2025, 6, 15), Decimal("0.25"), "USD"),
        Dividend(datetime(2025, 9, 15), datetime(2025, 9, 15), Decimal("0.25"), "USD"),
        Dividend(datetime(2025, 12, 15), datetime(2025, 12, 15), Decimal("0.25"), "USD"),
    ]
    ledger.register_unit(create_stock_unit(
        symbol="AAPL",
        name="Apple Inc",
        issuer="treasury",
        currency="USD",
        dividend_schedule=dividend_schedule,
        shortable=True,
    ))

    ledger.register_wallet("alice")
    ledger.register_wallet("bob")
    ledger.register_wallet("charlie")
    ledger.register_wallet("treasury")

    # Distribute shares
    ledger.set_balance("alice", "AAPL", Decimal("1000"))
    ledger.set_balance("bob", "AAPL", Decimal("500"))
    ledger.set_balance("charlie", "AAPL", Decimal("250"))
    ledger.set_balance("treasury", "USD", Decimal("10000000"))

    return ledger


# =============================================================================
# OPTIONS FIXTURES
# =============================================================================

@pytest.fixture
def option_ledger():
    """Ledger with bilateral option ready for testing."""
    ledger = Ledger("options", datetime(2025, 1, 1), verbose=False, test_mode=True)
    ledger.register_unit(cash("USD", "US Dollar", decimal_places=2))
    ledger.register_unit(create_stock("AAPL", "Apple Inc", "treasury", shortable=True))

    # Create option
    option = create_option_unit(
        symbol="AAPL_C150",
        name="AAPL Call $150",
        underlying="AAPL",
        strike=Decimal("150"),
        maturity=datetime(2025, 6, 20),
        option_type="call",
        quantity=Decimal("100"),  # Per contract
        currency="USD",
        long_wallet="alice",
        short_wallet="bob",
    )
    ledger.register_unit(option)

    # Register wallets
    ledger.register_wallet("alice")
    ledger.register_wallet("bob")
    ledger.register_wallet("treasury")

    # Fund wallets
    ledger.set_balance("alice", "USD", Decimal("100000"))
    ledger.set_balance("alice", "AAPL_C150", Decimal("5"))  # Long 5 contracts
    ledger.set_balance("bob", "AAPL_C150", Decimal("-5"))  # Short 5 contracts
    ledger.set_balance("bob", "AAPL", Decimal("1000"))  # Can deliver

    return ledger


@pytest.fixture
def put_option_ledger():
    """Ledger with put option for testing."""
    ledger = Ledger("put_options", datetime(2025, 1, 1), verbose=False, test_mode=True)
    ledger.register_unit(cash("USD", "US Dollar", decimal_places=2))
    ledger.register_unit(create_stock("AAPL", "Apple Inc", "treasury", shortable=True))

    # Create put option
    option = create_option_unit(
        symbol="AAPL_P150",
        name="AAPL Put $150",
        underlying="AAPL",
        strike=Decimal("150"),
        maturity=datetime(2025, 6, 20),
        option_type="put",
        quantity=Decimal("100"),
        currency="USD",
        long_wallet="alice",
        short_wallet="bob",
    )
    ledger.register_unit(option)

    ledger.register_wallet("alice")
    ledger.register_wallet("bob")
    ledger.register_wallet("treasury")

    ledger.set_balance("alice", "USD", Decimal("100000"))
    ledger.set_balance("alice", "AAPL", Decimal("1000"))  # Can deliver for put
    ledger.set_balance("alice", "AAPL_P150", Decimal("5"))
    ledger.set_balance("bob", "AAPL_P150", Decimal("-5"))
    ledger.set_balance("bob", "USD", Decimal("100000"))  # Cash for put assignment

    return ledger


# =============================================================================
# FORWARDS FIXTURES
# =============================================================================

@pytest.fixture
def forward_ledger():
    """Ledger with forward contract for testing."""
    ledger = Ledger("forwards", datetime(2025, 1, 1), verbose=False, test_mode=True)
    ledger.register_unit(cash("USD", "US Dollar", decimal_places=2))
    ledger.register_unit(create_stock("AAPL", "Apple Inc", "treasury", shortable=True))

    # Create forward contract
    forward = create_forward_unit(
        symbol="AAPL_FWD",
        name="AAPL Forward",
        underlying="AAPL",
        forward_price=Decimal("160"),
        delivery_date=datetime(2025, 6, 20),
        quantity=Decimal("100"),
        currency="USD",
        long_wallet="alice",
        short_wallet="bob",
    )
    ledger.register_unit(forward)

    ledger.register_wallet("alice")
    ledger.register_wallet("bob")
    ledger.register_wallet("treasury")

    ledger.set_balance("alice", "USD", Decimal("100000"))
    ledger.set_balance("alice", "AAPL_FWD", Decimal("5"))
    ledger.set_balance("bob", "AAPL_FWD", Decimal("-5"))
    ledger.set_balance("bob", "AAPL", Decimal("1000"))

    return ledger


# =============================================================================
# DELTA HEDGE FIXTURES
# =============================================================================

@pytest.fixture
def delta_hedge_ledger():
    """Ledger with delta hedge strategy for testing."""
    ledger = Ledger("delta_hedge", datetime(2025, 1, 1), verbose=False, test_mode=True)
    ledger.register_unit(cash("USD", "US Dollar", decimal_places=2))
    ledger.register_unit(create_stock("AAPL", "Apple Inc", "treasury", shortable=True))

    # Create delta hedge strategy
    hedge = create_delta_hedge_unit(
        symbol="HEDGE_AAPL",
        name="AAPL Delta Hedge",
        underlying="AAPL",
        strike=Decimal("150"),
        maturity=datetime(2025, 6, 20),
        volatility=Decimal("0.25"),
        num_options=Decimal("10"),
        option_multiplier=Decimal("100"),
        currency="USD",
        strategy_wallet="trader",
        market_wallet="market",
        risk_free_rate=Decimal("0"),
    )
    ledger.register_unit(hedge)

    ledger.register_wallet("trader")
    ledger.register_wallet("market")
    ledger.register_wallet("treasury")

    ledger.set_balance("trader", "USD", Decimal("500000"))
    ledger.set_balance("market", "USD", Decimal("10000000"))
    ledger.set_balance("market", "AAPL", Decimal("100000"))

    return ledger


# =============================================================================
# ENGINE FIXTURES
# =============================================================================

@pytest.fixture
def lifecycle_engine(trading_ledger):
    """LifecycleEngine with all contract types registered."""
    engine = LifecycleEngine(trading_ledger)
    engine.register("STOCK", stock_contract)
    engine.register("BILATERAL_OPTION", option_contract)
    engine.register("BILATERAL_FORWARD", forward_contract)
    engine.register("DELTA_HEDGE_STRATEGY", delta_hedge_contract(min_trade_size=0.01))
    return engine, trading_ledger


@pytest.fixture
def option_engine(option_ledger):
    """LifecycleEngine for option testing."""
    engine = LifecycleEngine(option_ledger)
    engine.register("BILATERAL_OPTION", option_contract)
    return engine, option_ledger


@pytest.fixture
def dividend_engine(dividend_ledger):
    """LifecycleEngine for dividend testing."""
    engine = LifecycleEngine(dividend_ledger)
    engine.register("STOCK", stock_contract)
    return engine, dividend_ledger


# =============================================================================
# PRICING FIXTURES
# =============================================================================

@pytest.fixture
def simple_price_path():
    """Simple price path for testing."""
    t0 = datetime(2025, 1, 1)
    prices = [
        (t0, Decimal("150")),
        (t0 + timedelta(days=1), Decimal("152")),
        (t0 + timedelta(days=2), Decimal("148")),
        (t0 + timedelta(days=3), Decimal("155")),
        (t0 + timedelta(days=4), Decimal("153")),
        (t0 + timedelta(days=5), Decimal("158")),
    ]
    return TimeSeriesPricingSource({"AAPL": prices}, base_currency="USD")


@pytest.fixture
def volatile_price_path():
    """More volatile price path for stress testing."""
    import random
    random.seed(42)

    t0 = datetime(2025, 1, 1)
    prices = []
    price = Decimal("150")
    for i in range(180):  # ~6 months
        prices.append((t0 + timedelta(days=i), price))
        # Daily return with 30% annualized vol
        daily_return = Decimal(str(random.gauss(0, 0.019)))  # ~0.30/sqrt(252)
        price *= (Decimal("1") + daily_return)

    return TimeSeriesPricingSource({"AAPL": prices}, base_currency="USD")


# =============================================================================
# FAKE VIEW FIXTURES
# =============================================================================

@pytest.fixture
def stock_view():
    """FakeView for stock dividend testing."""
    return FakeView(
        balances={
            "alice": {"AAPL": Decimal("1000"), "USD": Decimal("50000")},
            "bob": {"AAPL": Decimal("500")},
            "treasury": {"USD": Decimal("10000000")},
        },
        states={
            "AAPL": {
                "unit_type": "STOCK",
                "issuer": "treasury",
                "currency": "USD",
                "dividend_schedule": [Dividend(datetime(2025, 3, 15), datetime(2025, 3, 15), Decimal("0.25"), "USD")],
                "snapshots": {},
                "paid": {},
            }
        },
        time=datetime(2025, 3, 15)
    )


@pytest.fixture
def option_view():
    """FakeView for option settlement testing."""
    return FakeView(
        balances={
            "alice": {"OPT": Decimal("5"), "USD": Decimal("100000")},
            "bob": {"OPT": Decimal("-5"), "AAPL": Decimal("1000"), "USD": Decimal("50000")},
        },
        states={
            "OPT": {
                "unit_type": "BILATERAL_OPTION",
                "underlying": "AAPL",
                "strike": Decimal("150"),
                "maturity": datetime(2025, 6, 20),
                "option_type": "call",
                "quantity": Decimal("100"),
                "currency": "USD",
                "long_wallet": "alice",
                "short_wallet": "bob",
                "settled": False,
                "exercised": False,
            }
        },
        time=datetime(2025, 6, 20)
    )
