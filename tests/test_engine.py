"""
test_engine.py - Unit tests for LifecycleEngine

Tests:
- LifecycleEngine: contract registration, step execution, run over multiple timestamps
- Integration with SmartContract implementations (options, forwards, delta hedging)
"""

import pytest
from datetime import datetime, timedelta
from ledger import (
    Ledger, Move, ContractResult,
    LifecycleEngine, SmartContract,
    option_contract, forward_contract, delta_hedge_contract,
    create_option_unit,
    create_forward_unit,
    create_delta_hedge_unit,
    create_stock_unit,
    cash,
)


# Helper for creating test stocks
def _stock(symbol: str, name: str, issuer: str, shortable: bool = False):
    """Create a stock unit for testing."""
    return create_stock_unit(symbol, name, issuer, "USD", shortable=shortable)


class MockContract:
    """Mock SmartContract for testing."""

    def __init__(self, should_fire=False, moves=None, state_updates=None):
        self.should_fire = should_fire
        self.moves = moves or []
        self.state_updates = state_updates or {}
        self.call_count = 0

    def check_lifecycle(self, view, symbol, t, prices):
        self.call_count += 1
        if self.should_fire:
            return ContractResult(moves=self.moves, state_updates=self.state_updates)
        return ContractResult()


class TestLifecycleEngineBasic:
    """Basic tests for LifecycleEngine."""

    def test_create_engine(self):
        ledger = Ledger("test", no_log=True)
        engine = LifecycleEngine(ledger)
        assert engine.ledger is ledger
        assert engine.contracts == {}

    def test_create_engine_with_contracts(self):
        ledger = Ledger("test", no_log=True)
        mock_contract = MockContract()
        engine = LifecycleEngine(ledger, contracts={'MOCK': mock_contract})
        assert 'MOCK' in engine.contracts

    def test_register_contract(self):
        ledger = Ledger("test", no_log=True)
        engine = LifecycleEngine(ledger)
        mock_contract = MockContract()
        engine.register('MOCK_TYPE', mock_contract)
        assert 'MOCK_TYPE' in engine.contracts
        assert engine.contracts['MOCK_TYPE'] is mock_contract


class TestLifecycleEngineStep:
    """Tests for LifecycleEngine.step()."""

    def test_step_advances_time(self):
        ledger = Ledger("test", no_log=True)
        engine = LifecycleEngine(ledger)

        t1 = datetime(2025, 1, 15, 10, 0)
        engine.step(t1, {})
        assert ledger.current_time == t1

    def test_step_no_contracts_returns_empty(self):
        ledger = Ledger("test", no_log=True)
        engine = LifecycleEngine(ledger)

        txs = engine.step(datetime(2025, 1, 15), {})
        assert txs == []

    def test_step_contract_not_matched(self):
        ledger = Ledger("test", no_log=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        engine = LifecycleEngine(ledger)
        engine.register('OTHER_TYPE', MockContract(should_fire=True))

        # USD has unit_type='CASH', not 'OTHER_TYPE'
        txs = engine.step(datetime(2025, 1, 15), {})
        assert txs == []

    def test_step_contract_fires(self):
        ledger = Ledger("test", no_log=False, verbose=False)  # Enable logging to get transactions
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.balances["alice"]["USD"] = 1000

        # Create mock contract that fires
        mock_contract = MockContract(
            should_fire=True,
            moves=[Move("alice", "bob", "USD", 100.0, "mock_tx")]
        )
        engine = LifecycleEngine(ledger)
        engine.register('CASH', mock_contract)

        txs = engine.step(datetime(2025, 1, 15), {})
        assert len(txs) == 1
        assert ledger.get_balance("alice", "USD") == 900
        assert ledger.get_balance("bob", "USD") == 100

    def test_step_contract_not_firing(self):
        ledger = Ledger("test", no_log=True)
        ledger.register_unit(cash("USD", "US Dollar"))

        mock_contract = MockContract(should_fire=False)
        engine = LifecycleEngine(ledger)
        engine.register('CASH', mock_contract)

        txs = engine.step(datetime(2025, 1, 15), {})
        assert txs == []
        assert mock_contract.call_count == 1


class TestLifecycleEngineRun:
    """Tests for LifecycleEngine.run()."""

    def test_run_processes_all_timestamps(self):
        ledger = Ledger("test", no_log=True)
        ledger.register_unit(cash("USD", "US Dollar"))

        mock_contract = MockContract(should_fire=False)
        engine = LifecycleEngine(ledger)
        engine.register('CASH', mock_contract)

        timestamps = [
            datetime(2025, 1, 1),
            datetime(2025, 1, 2),
            datetime(2025, 1, 3),
        ]

        def price_fn(t):
            return {'USD': 1.0}

        engine.run(timestamps, price_fn)
        # Called once per timestamp
        assert mock_contract.call_count == 3
        assert ledger.current_time == timestamps[-1]

    def test_run_returns_all_transactions(self):
        ledger = Ledger("test", no_log=False, verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.balances["alice"]["USD"] = 10000

        # Contract that always fires
        mock_contract = MockContract(
            should_fire=True,
            moves=[Move("alice", "bob", "USD", 100.0, "mock_tx")]
        )
        engine = LifecycleEngine(ledger)
        engine.register('CASH', mock_contract)

        timestamps = [
            datetime(2025, 1, 1),
            datetime(2025, 1, 2),
            datetime(2025, 1, 3),
        ]

        def price_fn(t):
            return {}

        txs = engine.run(timestamps, price_fn)
        assert len(txs) == 3
        assert ledger.get_balance("alice", "USD") == 10000 - 300


class TestLifecycleEngineWithOptions:
    """Integration tests with OptionContract."""

    def test_option_auto_settlement(self):
        ledger = Ledger("test", no_log=False, verbose=False)

        # Setup units and wallets
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(_stock("AAPL", "Apple Inc.", "treasury"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("treasury")

        # Create option
        option_unit = create_option_unit(
            symbol="AAPL_C150",
            name="AAPL Call 150",
            underlying="AAPL",
            strike=150.0,
            maturity=datetime(2025, 6, 1),
            option_type="call",
            quantity=100,
            currency="USD",
            long_wallet="alice",
            short_wallet="bob"
        )
        ledger.register_unit(option_unit)

        # Setup positions
        ledger.balances["alice"]["AAPL_C150"] = 5
        ledger.balances["bob"]["AAPL_C150"] = -5
        ledger.balances["alice"]["USD"] = 100000
        ledger.balances["bob"]["AAPL"] = 1000

        # Setup engine
        engine = LifecycleEngine(ledger)
        engine.register("BILATERAL_OPTION", option_contract)

        # Run until maturity
        timestamps = [
            datetime(2025, 5, 30),
            datetime(2025, 5, 31),
            datetime(2025, 6, 1),  # Maturity
        ]

        def price_fn(t):
            return {'AAPL': 170.0}  # ITM

        txs = engine.run(timestamps, price_fn)

        # Should have settled at maturity
        state = ledger.get_unit_state("AAPL_C150")
        assert state.get('settled') is True


class TestLifecycleEngineWithForwards:
    """Integration tests with ForwardContract."""

    def test_forward_auto_settlement(self):
        ledger = Ledger("test", no_log=False, verbose=False)

        # Setup units and wallets
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(_stock("OIL", "Oil Barrel", "producer"))
        ledger.register_wallet("buyer")
        ledger.register_wallet("seller")
        ledger.register_wallet("producer")

        # Create forward
        forward_unit = create_forward_unit(
            symbol="OIL_FWD",
            name="Oil Forward",
            underlying="OIL",
            forward_price=75.0,
            delivery_date=datetime(2025, 6, 1),
            quantity=1000,
            currency="USD",
            long_wallet="buyer",
            short_wallet="seller"
        )
        ledger.register_unit(forward_unit)

        # Setup positions
        ledger.balances["buyer"]["OIL_FWD"] = 2
        ledger.balances["seller"]["OIL_FWD"] = -2
        ledger.balances["buyer"]["USD"] = 200000
        ledger.balances["seller"]["OIL"] = 5000

        # Setup engine
        engine = LifecycleEngine(ledger)
        engine.register("BILATERAL_FORWARD", forward_contract)

        # Run until delivery
        timestamps = [
            datetime(2025, 5, 30),
            datetime(2025, 5, 31),
            datetime(2025, 6, 1),  # Delivery date
        ]

        def price_fn(t):
            return {'OIL': 80.0}

        txs = engine.run(timestamps, price_fn)

        # Should have settled
        state = ledger.get_unit_state("OIL_FWD")
        assert state.get('settled') is True


class TestLifecycleEngineWithDeltaHedge:
    """Integration tests with DeltaHedgeContract."""

    def test_delta_hedge_rebalancing(self):
        ledger = Ledger("test", no_log=False, verbose=False)

        # Setup units and wallets
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(_stock("AAPL", "Apple Inc.", "treasury"))
        ledger.register_wallet("hedge_fund")
        ledger.register_wallet("market")
        ledger.register_wallet("treasury")

        # Create hedge
        maturity = datetime(2025, 6, 1)
        hedge_unit = create_delta_hedge_unit(
            symbol="HEDGE",
            name="AAPL Hedge",
            underlying="AAPL",
            strike=150.0,
            maturity=maturity,
            volatility=0.20,
            num_options=10,
            option_multiplier=100,
            currency="USD",
            strategy_wallet="hedge_fund",
            market_wallet="market",
            risk_free_rate=0.0,
        )
        ledger.register_unit(hedge_unit)

        # Setup balances
        ledger.balances["hedge_fund"]["USD"] = 1000000
        ledger.balances["market"]["AAPL"] = 100000
        ledger.balances["market"]["USD"] = 1000000

        # Setup engine
        engine = LifecycleEngine(ledger)
        engine.register("DELTA_HEDGE_STRATEGY", delta_hedge_contract(min_trade_size=0.01))

        # Run for a few days
        timestamps = [
            datetime(2025, 1, 1),
            datetime(2025, 1, 2),
            datetime(2025, 1, 3),
        ]

        def price_fn(t):
            return {'AAPL': 155.0}

        txs = engine.run(timestamps, price_fn)

        # Should have rebalanced (bought shares)
        assert ledger.get_balance("hedge_fund", "AAPL") > 0

    def test_delta_hedge_liquidation_at_maturity(self):
        ledger = Ledger("test", no_log=False, verbose=False)

        # Setup
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(_stock("AAPL", "Apple Inc.", "treasury"))
        ledger.register_wallet("hedge_fund")
        ledger.register_wallet("market")
        ledger.register_wallet("treasury")

        maturity = datetime(2025, 6, 1)
        hedge_unit = create_delta_hedge_unit(
            symbol="HEDGE",
            name="AAPL Hedge",
            underlying="AAPL",
            strike=150.0,
            maturity=maturity,
            volatility=0.20,
            num_options=10,
            option_multiplier=100,
            currency="USD",
            strategy_wallet="hedge_fund",
            market_wallet="market",
            risk_free_rate=0.0,
        )
        ledger.register_unit(hedge_unit)

        # Setup with existing position - set both wallet balance and strategy's current_shares
        ledger.set_balance("hedge_fund", "AAPL", 800)
        ledger.set_balance("hedge_fund", "USD", 50000)
        ledger.set_balance("market", "AAPL", 100000)  # Market needs AAPL to buy from hedge
        ledger.set_balance("market", "USD", 1000000)

        # Each strategy tracks its own shares in state
        # Access unit._state directly since get_unit_state() returns a deep copy
        ledger.units["HEDGE"]._state['current_shares'] = 800.0

        engine = LifecycleEngine(ledger)
        engine.register("DELTA_HEDGE_STRATEGY", delta_hedge_contract())

        # Run to maturity
        timestamps = [
            datetime(2025, 5, 31),
            datetime(2025, 6, 1),  # Maturity
        ]

        def price_fn(t):
            return {'AAPL': 160.0}

        engine.run(timestamps, price_fn)

        # Should be liquidated
        state = ledger.get_unit_state("HEDGE")
        assert state.get('liquidated') is True
        assert state.get('current_shares') == 0.0  # Strategy's tracked shares should be 0
        # Wallet should have 0 AAPL from this strategy (but test setup is a bit artificial)
        # The 800 shares were sold during liquidation
        assert ledger.get_balance("hedge_fund", "AAPL") == 0


class TestLifecycleEngineMultipleContracts:
    """Tests with multiple contract types."""

    def test_multiple_contract_types(self):
        ledger = Ledger("test", no_log=False, verbose=False)

        # Setup
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(_stock("AAPL", "Apple Inc.", "treasury"))
        ledger.register_unit(_stock("OIL", "Oil Barrel", "producer"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("market")
        ledger.register_wallet("treasury")
        ledger.register_wallet("producer")

        # Create option
        option_unit = create_option_unit(
            symbol="AAPL_C150",
            name="AAPL Call 150",
            underlying="AAPL",
            strike=150.0,
            maturity=datetime(2025, 6, 1),
            option_type="call",
            quantity=100,
            currency="USD",
            long_wallet="alice",
            short_wallet="bob"
        )
        ledger.register_unit(option_unit)

        # Create forward
        forward_unit = create_forward_unit(
            symbol="OIL_FWD",
            name="Oil Forward",
            underlying="OIL",
            forward_price=75.0,
            delivery_date=datetime(2025, 6, 1),
            quantity=1000,
            currency="USD",
            long_wallet="alice",
            short_wallet="bob"
        )
        ledger.register_unit(forward_unit)

        # Setup positions
        ledger.balances["alice"]["AAPL_C150"] = 5
        ledger.balances["bob"]["AAPL_C150"] = -5
        ledger.balances["alice"]["OIL_FWD"] = 2
        ledger.balances["bob"]["OIL_FWD"] = -2
        ledger.balances["alice"]["USD"] = 500000
        ledger.balances["bob"]["AAPL"] = 1000
        ledger.balances["bob"]["OIL"] = 5000

        # Register both contracts
        engine = LifecycleEngine(ledger)
        engine.register("BILATERAL_OPTION", option_contract)
        engine.register("BILATERAL_FORWARD", forward_contract)

        # Run to maturity
        timestamps = [datetime(2025, 6, 1)]

        def price_fn(t):
            return {'AAPL': 170.0, 'OIL': 80.0}

        engine.run(timestamps, price_fn)

        # Both should be settled
        assert ledger.get_unit_state("AAPL_C150").get('settled') is True
        assert ledger.get_unit_state("OIL_FWD").get('settled') is True
