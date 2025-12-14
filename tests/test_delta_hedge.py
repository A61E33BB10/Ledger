"""
test_delta_hedge.py - Unit tests for delta_hedge_strategy.py

Tests:
- create_delta_hedge_unit: unit creation (creates delta hedging strategy units)
- compute_rebalance: rebalancing logic (adjusts hedge position based on delta)
- compute_liquidation: maturity liquidation (closes out hedge at expiration)
- Analysis functions: get_hedge_state, compute_hedge_pnl_breakdown
- delta_hedge_contract: SmartContract implementation (automated lifecycle management)
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from ledger import (
    Ledger, Move, cash,
    create_stock_unit,
    create_delta_hedge_unit,
    compute_rebalance, compute_liquidation,
    get_hedge_state, compute_hedge_pnl_breakdown,
    delta_hedge_contract,
    LifecycleEngine,
)
from .fake_view import FakeView


class TestCreateDeltaHedgeUnit:
    """Tests for create_delta_hedge_unit factory."""

    def test_create_hedge_unit(self):
        unit = create_delta_hedge_unit(
            symbol="AAPL_HEDGE_150",
            name="AAPL Delta Hedge",
            underlying="AAPL",
            strike=Decimal("150.0"),
            maturity=datetime(2025, 12, 19),
            volatility=Decimal("0.20"),
            num_options=Decimal("10"),
            option_multiplier=Decimal("100"),
            currency="USD",
            strategy_wallet="hedge_fund",
            market_wallet="market",
        )

        assert unit.symbol == "AAPL_HEDGE_150"
        assert unit.name == "AAPL Delta Hedge"
        assert unit.unit_type == "DELTA_HEDGE_STRATEGY"
        assert unit.state['underlying'] == "AAPL"
        assert unit.state['strike'] == Decimal("150.0")
        assert unit.state['volatility'] == Decimal("0.20")
        assert unit.state['current_shares'] == Decimal("0.0")
        assert unit.state['cumulative_cash'] == Decimal("0.0")
        assert unit.state['rebalance_count'] == 0
        assert unit.state['liquidated'] is False


class TestComputeRebalance:
    """Tests for compute_rebalance function."""

    def test_rebalance_buy_shares(self):
        """When delta increases, we need to buy shares."""
        maturity = datetime(2025, 12, 19)
        view = FakeView(
            balances={
                'hedge_fund': {'AAPL': Decimal("0"), 'USD': Decimal("1000000")},
                'market': {'AAPL': Decimal("100000"), 'USD': Decimal("1000000")},
            },
            states={
                'HEDGE': {
                    'underlying': 'AAPL',
                    'strike': Decimal("150.0"),
                    'maturity': maturity,
                    'volatility': Decimal("0.20"),
                    'risk_free_rate': Decimal("0.0"),
                    'num_options': Decimal("10"),
                    'option_multiplier': Decimal("100"),
                    'currency': 'USD',
                    'strategy_wallet': 'hedge_fund',
                    'market_wallet': 'market',
                    'current_shares': Decimal("0.0"),
                    'cumulative_cash': Decimal("0.0"),
                    'rebalance_count': Decimal("0"),
                    'liquidated': False,
                }
            },
            time=datetime(2025, 1, 1)
        )
        result = compute_rebalance(view, 'HEDGE', spot_price=Decimal("150.0"))

        assert not result.is_empty()
        assert len(result.moves) == 2

        # First move: buy shares
        buy_move = next(m for m in result.moves if m.unit_symbol == 'AAPL')
        assert buy_move.source == 'market'
        assert buy_move.dest == 'hedge_fund'
        assert buy_move.quantity > 0

        # State update should track current_shares
        sc = next(d for d in result.state_changes if d.unit == "HEDGE")
        assert sc.new_state['current_shares'] == buy_move.quantity

        # Second move: pay for shares
        pay_move = next(m for m in result.moves if m.unit_symbol == 'USD')
        assert pay_move.source == 'hedge_fund'
        assert pay_move.dest == 'market'

    def test_rebalance_sell_shares(self):
        """When delta decreases, we need to sell shares."""
        maturity = datetime(2025, 12, 19)
        view = FakeView(
            balances={
                'hedge_fund': {'AAPL': Decimal("1000"), 'USD': Decimal("1000000")},
                'market': {'AAPL': Decimal("100000"), 'USD': Decimal("1000000")},
            },
            states={
                'HEDGE': {
                    'underlying': 'AAPL',
                    'strike': Decimal("150.0"),
                    'maturity': maturity,
                    'volatility': Decimal("0.20"),
                    'risk_free_rate': Decimal("0.0"),
                    'num_options': Decimal("10"),
                    'option_multiplier': Decimal("100"),
                    'currency': 'USD',
                    'strategy_wallet': 'hedge_fund',
                    'market_wallet': 'market',
                    'current_shares': Decimal("1000.0"),
                    'cumulative_cash': -100000.0,
                    'rebalance_count': Decimal("5"),
                    'liquidated': False,
                }
            },
            time=datetime(2025, 1, 1)
        )
        # Deep OTM, delta should be low
        result = compute_rebalance(view, 'HEDGE', spot_price=Decimal("100.0"))

        if not result.is_empty():
            # First move: sell shares
            sell_move = next(m for m in result.moves if m.unit_symbol == 'AAPL')
            assert sell_move.source == 'hedge_fund'
            assert sell_move.dest == 'market'

    def test_rebalance_at_maturity_returns_empty(self):
        """No rebalancing at/after maturity."""
        maturity = datetime(2025, 6, 1)
        view = FakeView(
            balances={
                'hedge_fund': {'AAPL': Decimal("500"), 'USD': Decimal("100000")},
                'market': {'AAPL': Decimal("100000")},
            },
            states={
                'HEDGE': {
                    'underlying': 'AAPL',
                    'strike': Decimal("150.0"),
                    'maturity': maturity,
                    'volatility': Decimal("0.20"),
                    'risk_free_rate': Decimal("0.0"),
                    'num_options': Decimal("10"),
                    'option_multiplier': Decimal("100"),
                    'currency': 'USD',
                    'strategy_wallet': 'hedge_fund',
                    'market_wallet': 'market',
                    'current_shares': Decimal("500.0"),
                    'cumulative_cash': Decimal("0.0"),
                    'rebalance_count': Decimal("10"),
                    'liquidated': False,
                }
            },
            time=datetime(2025, 6, 1)
        )
        result = compute_rebalance(view, 'HEDGE', spot_price=Decimal("160.0"))
        assert result.is_empty()

    def test_rebalance_liquidated_returns_empty(self):
        """No rebalancing if already liquidated."""
        maturity = datetime(2025, 12, 19)
        view = FakeView(
            balances={
                'hedge_fund': {'AAPL': Decimal("0"), 'USD': Decimal("100000")},
                'market': {'AAPL': Decimal("100000")},
            },
            states={
                'HEDGE': {
                    'underlying': 'AAPL',
                    'strike': Decimal("150.0"),
                    'maturity': maturity,
                    'volatility': Decimal("0.20"),
                    'risk_free_rate': Decimal("0.0"),
                    'num_options': Decimal("10"),
                    'option_multiplier': Decimal("100"),
                    'currency': 'USD',
                    'strategy_wallet': 'hedge_fund',
                    'market_wallet': 'market',
                    'current_shares': Decimal("0.0"),
                    'cumulative_cash': Decimal("50000.0"),
                    'rebalance_count': Decimal("20"),
                    'liquidated': True,
                }
            },
            time=datetime(2025, 1, 1)
        )
        result = compute_rebalance(view, 'HEDGE', spot_price=Decimal("160.0"))
        assert result.is_empty()

    def test_rebalance_updates_state(self):
        """Check state updates after rebalance."""
        maturity = datetime(2025, 12, 19)
        view = FakeView(
            balances={
                'hedge_fund': {'AAPL': Decimal("0"), 'USD': Decimal("1000000")},
                'market': {'AAPL': Decimal("100000"), 'USD': Decimal("1000000")},
            },
            states={
                'HEDGE': {
                    'underlying': 'AAPL',
                    'strike': Decimal("150.0"),
                    'maturity': maturity,
                    'volatility': Decimal("0.20"),
                    'risk_free_rate': Decimal("0.0"),
                    'num_options': Decimal("10"),
                    'option_multiplier': Decimal("100"),
                    'currency': 'USD',
                    'strategy_wallet': 'hedge_fund',
                    'market_wallet': 'market',
                    'current_shares': Decimal("0.0"),
                    'cumulative_cash': Decimal("0.0"),
                    'rebalance_count': Decimal("0"),
                    'liquidated': False,
                }
            },
            time=datetime(2025, 1, 1)
        )
        result = compute_rebalance(view, 'HEDGE', spot_price=Decimal("150.0"))

        if not result.is_empty():
            sc = next(d for d in result.state_changes if d.unit == "HEDGE")
            assert sc.new_state['rebalance_count'] == 1
            assert 'cumulative_cash' in sc.new_state

    def test_small_trade_filtered(self):
        """Trades below min_trade_size are filtered."""
        maturity = datetime(2025, 12, 19)
        view = FakeView(
            balances={
                'hedge_fund': {'AAPL': Decimal("500.0"), 'USD': Decimal("100000")},
                'market': {'AAPL': Decimal("100000")},
            },
            states={
                'HEDGE': {
                    'underlying': 'AAPL',
                    'strike': Decimal("150.0"),
                    'maturity': maturity,
                    'volatility': Decimal("0.20"),
                    'risk_free_rate': Decimal("0.0"),
                    'num_options': Decimal("10"),
                    'option_multiplier': Decimal("100"),
                    'currency': 'USD',
                    'strategy_wallet': 'hedge_fund',
                    'market_wallet': 'market',
                    'current_shares': Decimal("500.0"),
                    'cumulative_cash': Decimal("0.0"),
                    'rebalance_count': Decimal("0"),
                    'liquidated': False,
                }
            },
            time=datetime(2025, 1, 1)
        )
        # Use a very high min_trade_size
        result = compute_rebalance(view, 'HEDGE', spot_price=Decimal("150.0"), min_trade_size=Decimal("10000.0"))
        assert result.is_empty()


class TestComputeLiquidation:
    """Tests for compute_liquidation function."""

    def test_liquidation_sells_all_shares(self):
        view = FakeView(
            balances={
                'hedge_fund': {'AAPL': Decimal("800"), 'USD': Decimal("50000")},
                'market': {'AAPL': Decimal("100000"), 'USD': Decimal("1000000")},
            },
            states={
                'HEDGE': {
                    'underlying': 'AAPL',
                    'strike': Decimal("150.0"),
                    'maturity': datetime(2025, 6, 1),
                    'volatility': Decimal("0.20"),
                    'risk_free_rate': Decimal("0.0"),
                    'num_options': Decimal("10"),
                    'option_multiplier': Decimal("100"),
                    'currency': 'USD',
                    'strategy_wallet': 'hedge_fund',
                    'market_wallet': 'market',
                    'current_shares': Decimal("800.0"),
                    'cumulative_cash': -100000.0,
                    'rebalance_count': Decimal("20"),
                    'liquidated': False,
                }
            },
            time=datetime(2025, 6, 1)
        )
        result = compute_liquidation(view, 'HEDGE', spot_price=Decimal("160.0"))

        assert not result.is_empty()
        assert len(result.moves) == 2

        # Sell shares
        sell_move = next(m for m in result.moves if m.unit_symbol == 'AAPL')
        assert sell_move.source == 'hedge_fund'
        assert sell_move.dest == 'market'
        assert sell_move.quantity == Decimal("800")

        # Receive cash
        cash_move = next(m for m in result.moves if m.unit_symbol == 'USD')
        assert cash_move.source == 'market'
        assert cash_move.dest == 'hedge_fund'
        assert cash_move.quantity == Decimal("800") * Decimal("160.0")

        # State updates
        sc = next(d for d in result.state_changes if d.unit == "HEDGE")
        assert sc.new_state['liquidated'] is True
        assert sc.new_state['current_shares'] == Decimal("0.0")

    def test_liquidation_no_shares_marks_liquidated(self):
        """If no shares, just mark as liquidated."""
        view = FakeView(
            balances={
                'hedge_fund': {'AAPL': Decimal("0"), 'USD': Decimal("50000")},
                'market': {'AAPL': Decimal("100000")},
            },
            states={
                'HEDGE': {
                    'underlying': 'AAPL',
                    'strike': Decimal("150.0"),
                    'maturity': datetime(2025, 6, 1),
                    'volatility': Decimal("0.20"),
                    'risk_free_rate': Decimal("0.0"),
                    'num_options': Decimal("10"),
                    'option_multiplier': Decimal("100"),
                    'currency': 'USD',
                    'strategy_wallet': 'hedge_fund',
                    'market_wallet': 'market',
                    'current_shares': Decimal("0.0"),
                    'cumulative_cash': Decimal("0.0"),
                    'rebalance_count': Decimal("0"),
                    'liquidated': False,
                }
            },
            time=datetime(2025, 6, 1)
        )
        result = compute_liquidation(view, 'HEDGE', spot_price=Decimal("160.0"))

        assert not result.is_empty()
        assert len(result.moves) == 0
        sc = next(d for d in result.state_changes if d.unit == "HEDGE")
        assert sc.new_state['liquidated'] is True

    def test_liquidation_already_liquidated_returns_empty(self):
        view = FakeView(
            balances={
                'hedge_fund': {'AAPL': Decimal("0"), 'USD': Decimal("100000")},
                'market': {'AAPL': Decimal("100000")},
            },
            states={
                'HEDGE': {
                    'underlying': 'AAPL',
                    'strike': Decimal("150.0"),
                    'maturity': datetime(2025, 6, 1),
                    'volatility': Decimal("0.20"),
                    'risk_free_rate': Decimal("0.0"),
                    'num_options': Decimal("10"),
                    'option_multiplier': Decimal("100"),
                    'currency': 'USD',
                    'strategy_wallet': 'hedge_fund',
                    'market_wallet': 'market',
                    'current_shares': Decimal("0.0"),
                    'cumulative_cash': Decimal("50000.0"),
                    'rebalance_count': Decimal("20"),
                    'liquidated': True,
                }
            },
            time=datetime(2025, 6, 1)
        )
        result = compute_liquidation(view, 'HEDGE', spot_price=Decimal("160.0"))
        assert result.is_empty()


class TestGetHedgeState:
    """Tests for get_hedge_state function."""

    def test_get_hedge_state(self):
        maturity = datetime(2025, 12, 19)
        view = FakeView(
            balances={
                'hedge_fund': {'AAPL': Decimal("500"), 'USD': Decimal("50000")},
            },
            states={
                'HEDGE': {
                    'underlying': 'AAPL',
                    'strike': Decimal("150.0"),
                    'maturity': maturity,
                    'volatility': Decimal("0.20"),
                    'risk_free_rate': Decimal("0.0"),
                    'num_options': Decimal("10"),
                    'option_multiplier': Decimal("100"),
                    'currency': 'USD',
                    'strategy_wallet': 'hedge_fund',
                    'market_wallet': 'market',
                    'current_shares': Decimal("500.0"),
                    'cumulative_cash': -75000.0,
                    'rebalance_count': Decimal("10"),
                    'liquidated': False,
                }
            },
            time=datetime(2025, 1, 1)
        )
        state = get_hedge_state(view, 'HEDGE', spot_price=Decimal("155.0"))

        assert state['spot_price'] == Decimal("155.0")
        assert state['time_to_maturity_days'] > 0
        assert 0 <= float(state['delta']) <= 1
        assert state['current_shares'] == Decimal("500.0")
        assert state['cumulative_cash'] == Decimal("-75000.0")
        assert state['rebalance_count'] == 10
        assert state['liquidated'] is False
        assert 'option_value' in state
        assert 'shares_value' in state
        assert 'hedge_pnl' in state


class TestComputeHedgePnlBreakdown:
    """Tests for compute_hedge_pnl_breakdown function."""

    def test_pnl_breakdown_itm(self):
        view = FakeView(
            balances={
                'hedge_fund': {'AAPL': Decimal("1000"), 'USD': Decimal("50000")},
            },
            states={
                'HEDGE': {
                    'underlying': 'AAPL',
                    'strike': Decimal("150.0"),
                    'maturity': datetime(2025, 6, 1),
                    'volatility': Decimal("0.20"),
                    'risk_free_rate': Decimal("0.0"),
                    'num_options': Decimal("10"),
                    'option_multiplier': Decimal("100"),
                    'currency': 'USD',
                    'strategy_wallet': 'hedge_fund',
                    'market_wallet': 'market',
                    'current_shares': Decimal("1000.0"),
                    'cumulative_cash': -150000.0,
                    'rebalance_count': Decimal("20"),
                    'liquidated': False,
                }
            },
            time=datetime(2025, 6, 1)
        )
        pnl = compute_hedge_pnl_breakdown(view, 'HEDGE', final_spot=Decimal("170.0"))

        # Option payoff: (170 - 150) * 10 * 100 = 20000
        assert pnl['option_payoff'] == Decimal("20.0") * Decimal("10") * Decimal("100")
        assert pnl['final_spot'] == Decimal("170.0")
        assert pnl['shares_held'] == Decimal("1000.0")
        assert pnl['shares_value'] == Decimal("1000") * Decimal("170.0")
        assert pnl['cumulative_cash'] == Decimal("-150000.0")
        assert 'hedge_pnl' in pnl
        assert 'net_pnl' in pnl

    def test_pnl_breakdown_otm(self):
        view = FakeView(
            balances={
                'hedge_fund': {'AAPL': Decimal("100"), 'USD': Decimal("50000")},
            },
            states={
                'HEDGE': {
                    'underlying': 'AAPL',
                    'strike': Decimal("150.0"),
                    'maturity': datetime(2025, 6, 1),
                    'volatility': Decimal("0.20"),
                    'risk_free_rate': Decimal("0.0"),
                    'num_options': Decimal("10"),
                    'option_multiplier': Decimal("100"),
                    'currency': 'USD',
                    'strategy_wallet': 'hedge_fund',
                    'market_wallet': 'market',
                    'current_shares': Decimal("100.0"),
                    'cumulative_cash': -10000.0,
                    'rebalance_count': Decimal("20"),
                    'liquidated': False,
                }
            },
            time=datetime(2025, 6, 1)
        )
        pnl = compute_hedge_pnl_breakdown(view, 'HEDGE', final_spot=Decimal("140.0"))

        # Option payoff: max(0, 140 - 150) * 10 * 100 = 0
        assert pnl['option_payoff'] == Decimal("0.0")


class TestDeltaHedgeContract:
    """Tests for delta_hedge_contract SmartContract implementation."""

    def test_check_lifecycle_rebalance_before_maturity(self):
        maturity = datetime(2025, 12, 19)
        view = FakeView(
            balances={
                'hedge_fund': {'AAPL': Decimal("0"), 'USD': Decimal("1000000")},
                'market': {'AAPL': Decimal("100000"), 'USD': Decimal("1000000")},
            },
            states={
                'HEDGE': {
                    'underlying': 'AAPL',
                    'strike': Decimal("150.0"),
                    'maturity': maturity,
                    'volatility': Decimal("0.20"),
                    'risk_free_rate': Decimal("0.0"),
                    'num_options': Decimal("10"),
                    'option_multiplier': Decimal("100"),
                    'currency': 'USD',
                    'strategy_wallet': 'hedge_fund',
                    'market_wallet': 'market',
                    'current_shares': Decimal("0.0"),
                    'cumulative_cash': Decimal("0.0"),
                    'rebalance_count': Decimal("0"),
                    'liquidated': False,
                }
            },
            time=datetime(2025, 1, 1)
        )
        check = delta_hedge_contract(min_trade_size=Decimal("0.01"))
        result = check(view, 'HEDGE', datetime(2025, 1, 1), {'AAPL': Decimal("155.0")})
        # Should rebalance (buy shares)
        assert not result.is_empty()

    def test_check_lifecycle_liquidate_at_maturity(self):
        maturity = datetime(2025, 6, 1)
        view = FakeView(
            balances={
                'hedge_fund': {'AAPL': Decimal("800"), 'USD': Decimal("50000")},
                'market': {'AAPL': Decimal("100000"), 'USD': Decimal("1000000")},
            },
            states={
                'HEDGE': {
                    'underlying': 'AAPL',
                    'strike': Decimal("150.0"),
                    'maturity': maturity,
                    'volatility': Decimal("0.20"),
                    'risk_free_rate': Decimal("0.0"),
                    'num_options': Decimal("10"),
                    'option_multiplier': Decimal("100"),
                    'currency': 'USD',
                    'strategy_wallet': 'hedge_fund',
                    'market_wallet': 'market',
                    'current_shares': Decimal("800.0"),
                    'cumulative_cash': -100000.0,
                    'rebalance_count': Decimal("20"),
                    'liquidated': False,
                }
            },
            time=datetime(2025, 6, 1)
        )
        check = delta_hedge_contract()
        result = check(view, 'HEDGE', datetime(2025, 6, 1), {'AAPL': Decimal("160.0")})
        # Should liquidate
        assert not result.is_empty()
        sc = next(d for d in result.state_changes if d.unit == "HEDGE")
        assert sc.new_state['liquidated'] is True

    def test_check_lifecycle_already_liquidated(self):
        view = FakeView(
            balances={
                'hedge_fund': {'AAPL': Decimal("0"), 'USD': Decimal("100000")},
            },
            states={
                'HEDGE': {
                    'underlying': 'AAPL',
                    'strike': Decimal("150.0"),
                    'maturity': datetime(2025, 6, 1),
                    'volatility': Decimal("0.20"),
                    'risk_free_rate': Decimal("0.0"),
                    'num_options': Decimal("10"),
                    'option_multiplier': Decimal("100"),
                    'currency': 'USD',
                    'strategy_wallet': 'hedge_fund',
                    'market_wallet': 'market',
                    'current_shares': Decimal("0.0"),
                    'cumulative_cash': Decimal("50000.0"),
                    'rebalance_count': Decimal("20"),
                    'liquidated': True,
                }
            },
            time=datetime(2025, 6, 1)
        )
        check = delta_hedge_contract()
        result = check(view, 'HEDGE', datetime(2025, 6, 1), {'AAPL': Decimal("160.0")})
        assert result.is_empty()

    def test_check_lifecycle_missing_price_raises(self):
        maturity = datetime(2025, 12, 19)
        view = FakeView(
            balances={
                'hedge_fund': {'AAPL': Decimal("500"), 'USD': Decimal("50000")},
            },
            states={
                'HEDGE': {
                    'underlying': 'AAPL',
                    'strike': Decimal("150.0"),
                    'maturity': maturity,
                    'volatility': Decimal("0.20"),
                    'risk_free_rate': Decimal("0.0"),
                    'num_options': Decimal("10"),
                    'option_multiplier': Decimal("100"),
                    'currency': 'USD',
                    'strategy_wallet': 'hedge_fund',
                    'market_wallet': 'market',
                    'current_shares': Decimal("500.0"),
                    'cumulative_cash': Decimal("0.0"),
                    'rebalance_count': Decimal("0"),
                    'liquidated': False,
                }
            },
            time=datetime(2025, 1, 1)
        )
        check = delta_hedge_contract()
        # No AAPL price provided - should raise
        with pytest.raises(ValueError, match="Missing price for delta hedge underlying 'AAPL'"):
            check(view, 'HEDGE', datetime(2025, 1, 1), {'TSLA': Decimal("200.0")})


class TestMultipleStrategiesSameWallet:
    """
    Tests for multiple delta hedge strategies on the same underlying in the same wallet.

    Each strategy tracks its own shares independently.
    """

    def test_two_strategies_same_underlying_same_wallet_independent(self):
        """
        Two strategies on AAPL in the same wallet should each track their own shares.
        Each should buy the correct delta-adjusted amount.
        """
        maturity = datetime(2025, 12, 19)
        start_time = datetime(2025, 1, 1)

        # Create real ledger
        ledger = Ledger("multi_hedge_test", initial_time=start_time, verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_stock_unit(
            symbol="AAPL",
            name="Apple Inc.",
            issuer="market",
            currency="USD",
            shortable=True,
        ))

        # Setup wallets
        hedge_fund = ledger.register_wallet("hedge_fund")
        market = ledger.register_wallet("market")

        # Fund wallets
        ledger.set_balance(hedge_fund, "USD", 10_000_000)
        ledger.set_balance(market, "AAPL", 1_000_000)
        ledger.set_balance(market, "USD", 10_000_000)

        # Create two strategies with DIFFERENT strikes in SAME wallet
        ledger.register_unit(create_delta_hedge_unit(
            symbol="HEDGE_150",
            name="AAPL Hedge 150",
            underlying="AAPL",
            strike=Decimal("150.0"),
            maturity=maturity,
            volatility=Decimal("0.20"),
            num_options=Decimal("10"),
            option_multiplier=Decimal("100"),
            currency="USD",
            strategy_wallet=hedge_fund,
            market_wallet=market,
        ))

        ledger.register_unit(create_delta_hedge_unit(
            symbol="HEDGE_160",
            name="AAPL Hedge 160",
            underlying="AAPL",
            strike=Decimal("160.0"),
            maturity=maturity,
            volatility=Decimal("0.20"),
            num_options=Decimal("10"),
            option_multiplier=Decimal("100"),
            currency="USD",
            strategy_wallet=hedge_fund,  # SAME wallet
            market_wallet=market,
        ))

        # Setup engine
        engine = LifecycleEngine(ledger)
        engine.register("DELTA_HEDGE_STRATEGY", delta_hedge_contract(min_trade_size=Decimal("0.01")))

        # Run engine at spot = 155 (between the two strikes)
        spot_price = Decimal("155.0")
        txs = engine.step(start_time, {"AAPL": spot_price})

        # Both strategies should have executed
        assert len(txs) == 2, f"Expected 2 transactions, got {len(txs)}"

        # Get strategy states
        state_150 = ledger.get_unit_state("HEDGE_150")
        state_160 = ledger.get_unit_state("HEDGE_160")

        # Each strategy should have its own shares
        shares_150 = state_150.get('current_shares', Decimal("0"))
        shares_160 = state_160.get('current_shares', Decimal("0"))

        assert shares_150 > 0, "HEDGE_150 should have bought shares"
        assert shares_160 > 0, "HEDGE_160 should have bought shares"

        # HEDGE_150 (strike 150, spot 155) should have higher delta than HEDGE_160 (strike 160, spot 155)
        # Therefore HEDGE_150 should have more shares
        assert shares_150 > shares_160, f"ATM option (150) should have more shares than OTM (160), got {shares_150} vs {shares_160}"

        # The wallet's total AAPL should equal sum of both strategies' shares
        wallet_aapl = ledger.get_balance(hedge_fund, "AAPL")
        assert abs(float(wallet_aapl - (shares_150 + shares_160))) < 0.01, \
            f"Wallet AAPL ({wallet_aapl}) should equal sum of strategy shares ({shares_150 + shares_160})"

    def test_strategies_rebalance_independently(self):
        """
        When price changes, each strategy should rebalance based on its own position.
        """
        maturity = datetime(2025, 12, 19)
        start_time = datetime(2025, 1, 1)

        ledger = Ledger("multi_rebalance_test", initial_time=start_time, verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_stock_unit(
            symbol="AAPL",
            name="Apple Inc.",
            issuer="market",
            currency="USD",
            shortable=True,
        ))

        hedge_fund = ledger.register_wallet("hedge_fund")
        market = ledger.register_wallet("market")

        ledger.set_balance(hedge_fund, "USD", 10_000_000)
        ledger.set_balance(market, "AAPL", 1_000_000)
        ledger.set_balance(market, "USD", 10_000_000)

        # Two strategies with same strikes but different sizes
        ledger.register_unit(create_delta_hedge_unit(
            symbol="HEDGE_SMALL",
            name="Small Hedge",
            underlying="AAPL",
            strike=Decimal("150.0"),
            maturity=maturity,
            volatility=Decimal("0.20"),
            num_options=Decimal("5"),  # 5 options
            option_multiplier=Decimal("100"),
            currency="USD",
            strategy_wallet=hedge_fund,
            market_wallet=market,
        ))

        ledger.register_unit(create_delta_hedge_unit(
            symbol="HEDGE_LARGE",
            name="Large Hedge",
            underlying="AAPL",
            strike=Decimal("150.0"),
            maturity=maturity,
            volatility=Decimal("0.20"),
            num_options=Decimal("15"),  # 15 options
            option_multiplier=Decimal("100"),
            currency="USD",
            strategy_wallet=hedge_fund,
            market_wallet=market,
        ))

        engine = LifecycleEngine(ledger)
        engine.register("DELTA_HEDGE_STRATEGY", delta_hedge_contract(min_trade_size=Decimal("0.01")))

        # Initial rebalance
        engine.step(start_time, {"AAPL": Decimal("150.0")})

        shares_small_t1 = ledger.get_unit_state("HEDGE_SMALL")['current_shares']
        shares_large_t1 = ledger.get_unit_state("HEDGE_LARGE")['current_shares']

        # Large should have 3x the shares of small (15 vs 5 options)
        assert abs(float(shares_large_t1 / shares_small_t1) - 3.0) < 0.01, \
            f"Large should have 3x shares of small, got {shares_large_t1 / shares_small_t1}"

        # Price moves up - delta increases
        engine.step(datetime(2025, 1, 2), {"AAPL": Decimal("160.0")})

        shares_small_t2 = ledger.get_unit_state("HEDGE_SMALL")['current_shares']
        shares_large_t2 = ledger.get_unit_state("HEDGE_LARGE")['current_shares']

        # Both should have more shares after price increase
        assert shares_small_t2 > shares_small_t1, "Small hedge should have more shares after price increase"
        assert shares_large_t2 > shares_large_t1, "Large hedge should have more shares after price increase"

        # Ratio should still be 3:1
        assert abs(float(shares_large_t2 / shares_small_t2) - 3.0) < 0.01, \
            f"Ratio should still be 3:1, got {shares_large_t2 / shares_small_t2}"

    def test_one_strategy_liquidates_other_continues(self):
        """
        When one strategy reaches maturity and liquidates, the other should continue.
        """
        early_maturity = datetime(2025, 3, 1)
        late_maturity = datetime(2025, 6, 1)
        start_time = datetime(2025, 1, 1)

        ledger = Ledger("partial_liquidation_test", initial_time=start_time, verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_stock_unit(
            symbol="AAPL",
            name="Apple Inc.",
            issuer="market",
            currency="USD",
            shortable=True,
        ))

        hedge_fund = ledger.register_wallet("hedge_fund")
        market = ledger.register_wallet("market")

        ledger.set_balance(hedge_fund, "USD", 10_000_000)
        ledger.set_balance(market, "AAPL", 1_000_000)
        ledger.set_balance(market, "USD", 10_000_000)

        # Two strategies with different maturities
        ledger.register_unit(create_delta_hedge_unit(
            symbol="HEDGE_EARLY",
            name="Early Hedge",
            underlying="AAPL",
            strike=Decimal("150.0"),
            maturity=early_maturity,
            volatility=Decimal("0.20"),
            num_options=Decimal("10"),
            option_multiplier=Decimal("100"),
            currency="USD",
            strategy_wallet=hedge_fund,
            market_wallet=market,
        ))

        ledger.register_unit(create_delta_hedge_unit(
            symbol="HEDGE_LATE",
            name="Late Hedge",
            underlying="AAPL",
            strike=Decimal("150.0"),
            maturity=late_maturity,
            volatility=Decimal("0.20"),
            num_options=Decimal("10"),
            option_multiplier=Decimal("100"),
            currency="USD",
            strategy_wallet=hedge_fund,
            market_wallet=market,
        ))

        engine = LifecycleEngine(ledger)
        engine.register("DELTA_HEDGE_STRATEGY", delta_hedge_contract(min_trade_size=Decimal("0.01")))

        # Initial rebalance
        engine.step(start_time, {"AAPL": Decimal("150.0")})

        shares_early_t1 = ledger.get_unit_state("HEDGE_EARLY")['current_shares']
        shares_late_t1 = ledger.get_unit_state("HEDGE_LATE")['current_shares']

        assert shares_early_t1 > 0
        assert shares_late_t1 > 0

        # Move to early maturity - should liquidate early, rebalance late
        engine.step(early_maturity, {"AAPL": Decimal("155.0")})

        state_early = ledger.get_unit_state("HEDGE_EARLY")
        state_late = ledger.get_unit_state("HEDGE_LATE")

        assert state_early['liquidated'] is True, "Early hedge should be liquidated"
        assert state_early['current_shares'] == Decimal("0.0"), "Liquidated hedge should have 0 shares"
        assert state_late['liquidated'] is False, "Late hedge should NOT be liquidated"
        assert state_late['current_shares'] > 0, "Late hedge should still have shares"

        # Wallet should only have late hedge shares
        wallet_aapl = ledger.get_balance(hedge_fund, "AAPL")
        assert abs(float(wallet_aapl - state_late['current_shares'])) < 0.01, \
            f"Wallet AAPL ({wallet_aapl}) should equal late hedge shares ({state_late['current_shares']})"
