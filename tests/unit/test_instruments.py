"""
test_instruments.py - Unit tests for instrument modules

Tests pure functions for:
- Stocks: create_stock_unit, process_dividends
- Options: create_option_unit, compute_option_settlement
- Forwards: create_forward_unit, compute_forward_settlement
- Delta Hedge: create_delta_hedge_unit, compute_rebalance, compute_liquidation
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from ledger import (
    # Core
    PendingTransaction,

    # Stocks
    Dividend,
    create_stock_unit,
    process_dividends,
    stock_contract,

    # Options
    create_option_unit,
    compute_option_settlement,
    get_option_intrinsic_value,
    option_contract,

    # Forwards
    create_forward_unit,
    compute_forward_settlement,
    get_forward_value,
    forward_contract,

    # Delta Hedge
    create_delta_hedge_unit,
    compute_rebalance,
    compute_liquidation,
    get_hedge_state,
    compute_hedge_pnl_breakdown,
    delta_hedge_contract,
)
from tests.fake_view import FakeView


# =============================================================================
# STOCKS
# =============================================================================

class TestCreateStockUnit:
    """Tests for create_stock_unit factory."""

    def test_create_stock_basic(self):
        """Create basic stock unit."""
        unit = create_stock_unit("AAPL", "Apple Inc", "treasury", "USD")
        assert unit.symbol == "AAPL"
        assert unit.name == "Apple Inc"
        assert unit.unit_type == "STOCK"

    def test_create_stock_shortable(self):
        """Shortable stock allows negative balance."""
        unit = create_stock_unit("AAPL", "Apple Inc", "treasury", "USD", shortable=True)
        assert unit.min_balance < 0

    def test_create_stock_not_shortable(self):
        """Non-shortable stock has zero min_balance."""
        unit = create_stock_unit("AAPL", "Apple Inc", "treasury", "USD", shortable=False)
        assert unit.min_balance == Decimal("0")

    def test_create_stock_with_dividend_schedule(self):
        """Stock with dividend schedule."""
        schedule = [
            Dividend(datetime(2025, 3, 15), datetime(2025, 3, 15), 0.25, "USD"),
            Dividend(datetime(2025, 6, 15), datetime(2025, 6, 15), 0.25, "USD"),
        ]
        unit = create_stock_unit("AAPL", "Apple Inc", "treasury", "USD",
                                  dividend_schedule=schedule)
        state = unit.state
        assert len(state.get('dividend_schedule', [])) == 2

    def test_create_stock_state_has_issuer(self):
        """Stock state includes issuer."""
        unit = create_stock_unit("AAPL", "Apple Inc", "treasury", "USD")
        assert unit.state['issuer'] == "treasury"


class TestProcessDividends:
    """Tests for process_dividends pure function."""

    def test_dividend_on_payment_date(self):
        """Dividend paid on payment date."""
        view = FakeView(
            balances={
                "alice": {"AAPL": Decimal("1000")},
                "bob": {"AAPL": Decimal("500")},
                "treasury": {"USD": Decimal("10000000")},
            },
            states={
                "AAPL": {
                    "unit_type": "STOCK",
                    "issuer": "treasury",
                    "currency": "USD",
                    "dividend_schedule": [Dividend(datetime(2025, 3, 15), datetime(2025, 3, 15), 0.25, "USD")],
                    "snapshots": {},
                    "paid": {},
                }
            },
            time=datetime(2025, 3, 15)
        )

        result = process_dividends(view, "AAPL", datetime(2025, 3, 15))

        assert not result.is_empty()
        assert len(result.moves) == 2  # alice and bob

    def test_dividend_before_payment_date(self):
        """No dividend before payment date."""
        view = FakeView(
            balances={"alice": {"AAPL": Decimal("1000")}, "treasury": {"USD": Decimal("10000000")}},
            states={
                "AAPL": {
                    "unit_type": "STOCK",
                    "issuer": "treasury",
                    "currency": "USD",
                    "dividend_schedule": [Dividend(datetime(2025, 3, 15), datetime(2025, 3, 15), 0.25, "USD")],
                    "snapshots": {},
                    "paid": {},
                }
            },
            time=datetime(2025, 3, 14)
        )

        result = process_dividends(view, "AAPL", datetime(2025, 3, 14))
        assert result.is_empty()

    def test_dividend_correct_amount(self):
        """Dividend amount is shares × dividend_per_share."""
        view = FakeView(
            balances={
                "alice": {"AAPL": Decimal("1000")},
                "treasury": {"USD": Decimal("10000000")},
            },
            states={
                "AAPL": {
                    "unit_type": "STOCK",
                    "issuer": "treasury",
                    "currency": "USD",
                    "dividend_schedule": [Dividend(datetime(2025, 3, 15), datetime(2025, 3, 15), 0.25, "USD")],
                    "processed_dividends": [],
                }
            },
            time=datetime(2025, 3, 15)
        )

        result = process_dividends(view, "AAPL", datetime(2025, 3, 15))

        # alice: DeferredCash entitlement (qty=1)
        assert len(result.moves) == 1
        assert len(result.units_to_create) == 1
        # Check DeferredCash amount: 1000 shares × $0.25 = $250
        dc_unit = result.units_to_create[0]
        assert dc_unit.state["amount"] == 250.0

    def test_dividend_excludes_issuer(self):
        """Issuer doesn't receive dividend on own shares."""
        view = FakeView(
            balances={
                "alice": {"AAPL": Decimal("1000")},
                "treasury": {"AAPL": Decimal("5000"), "USD": Decimal("10000000")},
            },
            states={
                "AAPL": {
                    "unit_type": "STOCK",
                    "issuer": "treasury",
                    "currency": "USD",
                    "dividend_schedule": [Dividend(datetime(2025, 3, 15), datetime(2025, 3, 15), 0.25, "USD")],
                    "processed_dividends": [],
                }
            },
            time=datetime(2025, 3, 15)
        )

        result = process_dividends(view, "AAPL", datetime(2025, 3, 15))

        # Only alice gets dividend (DeferredCash), not treasury
        assert len(result.moves) == 1
        assert result.moves[0].dest == "alice"

    def test_dividend_tracks_processed(self):
        """State update tracks processed dividends."""
        view = FakeView(
            balances={
                "alice": {"AAPL": Decimal("1000")},
                "treasury": {"USD": Decimal("10000000")},
            },
            states={
                "AAPL": {
                    "unit_type": "STOCK",
                    "issuer": "treasury",
                    "currency": "USD",
                    "dividend_schedule": [Dividend(datetime(2025, 3, 15), datetime(2025, 3, 15), 0.25, "USD")],
                    "processed_dividends": [],
                }
            },
            time=datetime(2025, 3, 15)
        )

        result = process_dividends(view, "AAPL", datetime(2025, 3, 15))

        sc = next(d for d in result.state_changes if d.unit == "AAPL")
        # New format: just processed_dividends list
        assert "2025-03-15" in sc.new_state["processed_dividends"]

    def test_dividend_already_processed(self):
        """Empty result when dividend already processed."""
        view = FakeView(
            balances={
                "alice": {"AAPL": Decimal("1000")},
                "treasury": {"USD": Decimal("10000000")},
            },
            states={
                "AAPL": {
                    "unit_type": "STOCK",
                    "issuer": "treasury",
                    "currency": "USD",
                    "dividend_schedule": [Dividend(datetime(2025, 3, 15), datetime(2025, 3, 15), 0.25, "USD")],
                    "processed_dividends": ["2025-03-15"],
                }
            },
            time=datetime(2025, 6, 15)
        )

        result = process_dividends(view, "AAPL", datetime(2025, 6, 15))
        assert result.is_empty()


class TestStockContract:
    """Tests for stock_contract SmartContract interface."""

    def test_stock_contract_returns_contract_result(self):
        """stock_contract returns PendingTransaction."""
        view = FakeView(
            balances={"alice": {"AAPL": Decimal("1000")}, "treasury": {"USD": Decimal("10000000")}},
            states={
                "AAPL": {
                    "unit_type": "STOCK",
                    "issuer": "treasury",
                    "currency": "USD",
                    "dividend_schedule": [Dividend(datetime(2025, 3, 15), datetime(2025, 3, 15), 0.25, "USD")],
                    "snapshots": {},
                    "paid": {},
                }
            },
            time=datetime(2025, 3, 15)
        )

        result = stock_contract(view, "AAPL", datetime(2025, 3, 15), {"AAPL": Decimal("150.0")})

        assert isinstance(result, PendingTransaction)


# =============================================================================
# OPTIONS
# =============================================================================

class TestCreateOptionUnit:
    """Tests for create_option_unit factory."""

    def test_create_call_option(self):
        """Create call option."""
        unit = create_option_unit(
            symbol="AAPL_C150",
            name="AAPL Call $150",
            underlying="AAPL",
            strike=Decimal("150.0"),
            maturity=datetime(2025, 6, 20),
            option_type="call",
            quantity=Decimal("100"),
            currency="USD",
            long_wallet="alice",
            short_wallet="bob",
        )
        assert unit.symbol == "AAPL_C150"
        assert unit.unit_type == "BILATERAL_OPTION"
        assert unit.state['option_type'] == "call"

    def test_create_put_option(self):
        """Create put option."""
        unit = create_option_unit(
            symbol="AAPL_P150",
            name="AAPL Put $150",
            underlying="AAPL",
            strike=Decimal("150.0"),
            maturity=datetime(2025, 6, 20),
            option_type="put",
            quantity=Decimal("100"),
            currency="USD",
            long_wallet="alice",
            short_wallet="bob",
        )
        assert unit.state['option_type'] == "put"

    def test_create_option_invalid_type_raises(self):
        """Invalid option_type raises."""
        with pytest.raises(ValueError, match="option_type"):
            create_option_unit(
                symbol="OPT",
                name="Invalid",
                underlying="AAPL",
                strike=Decimal("150.0"),
                maturity=datetime(2025, 6, 20),
                option_type="invalid",
                quantity=Decimal("100"),
                currency="USD",
                long_wallet="alice",
                short_wallet="bob",
            )

    def test_create_option_has_bilateral_rule(self):
        """Option has bilateral transfer rule."""
        unit = create_option_unit(
            symbol="OPT",
            name="Test Option",
            underlying="AAPL",
            strike=Decimal("150.0"),
            maturity=datetime(2025, 6, 20),
            option_type="call",
            quantity=Decimal("100"),
            currency="USD",
            long_wallet="alice",
            short_wallet="bob",
        )
        assert unit.transfer_rule is not None


class TestComputeOptionSettlement:
    """Tests for compute_option_settlement pure function."""

    def test_call_itm_settlement(self):
        """ITM call option exercises."""
        view = FakeView(
            balances={
                "alice": {"OPT": Decimal("5"), "USD": Decimal("100000")},
                "bob": {"OPT": -5, "AAPL": Decimal("1000")},
            },
            states={
                "OPT": {
                    "unit_type": "BILATERAL_OPTION",
                    "underlying": "AAPL",
                    "strike": Decimal("150.0"),
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

        result = compute_option_settlement(view, "OPT", 170.0)

        assert not result.is_empty()
        # State should show exercised=True, settled=True
        sc = next(d for d in result.state_changes if d.unit == "OPT")
        assert sc.new_state["exercised"] is True
        assert sc.new_state["settled"] is True

    def test_call_otm_settlement(self):
        """OTM call option expires worthless."""
        view = FakeView(
            balances={
                "alice": {"OPT": Decimal("5"), "USD": Decimal("100000")},
                "bob": {"OPT": -5, "AAPL": Decimal("1000")},
            },
            states={
                "OPT": {
                    "unit_type": "BILATERAL_OPTION",
                    "underlying": "AAPL",
                    "strike": Decimal("150.0"),
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

        result = compute_option_settlement(view, "OPT", 140.0)

        # Should still settle but not exercise
        sc = next(d for d in result.state_changes if d.unit == "OPT")
        assert sc.new_state["settled"] is True
        assert sc.new_state["exercised"] is False

    def test_option_already_settled_empty(self):
        """Already settled option returns empty."""
        view = FakeView(
            balances={
                "alice": {"OPT": Decimal("0")},
                "bob": {"OPT": Decimal("0")},
            },
            states={
                "OPT": {
                    "unit_type": "BILATERAL_OPTION",
                    "underlying": "AAPL",
                    "strike": Decimal("150.0"),
                    "maturity": datetime(2025, 6, 20),
                    "option_type": "call",
                    "quantity": Decimal("100"),
                    "currency": "USD",
                    "long_wallet": "alice",
                    "short_wallet": "bob",
                    "settled": True,
                    "exercised": True,
                }
            },
            time=datetime(2025, 6, 20)
        )

        result = compute_option_settlement(view, "OPT", 170.0)
        assert result.is_empty()

    def test_option_before_maturity_empty(self):
        """Option before maturity returns empty."""
        view = FakeView(
            balances={
                "alice": {"OPT": Decimal("5")},
                "bob": {"OPT": -5},
            },
            states={
                "OPT": {
                    "unit_type": "BILATERAL_OPTION",
                    "underlying": "AAPL",
                    "strike": Decimal("150.0"),
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
            time=datetime(2025, 6, 19)
        )

        result = compute_option_settlement(view, "OPT", 170.0)
        assert result.is_empty()


class TestGetOptionIntrinsicValue:
    """Tests for get_option_intrinsic_value."""

    def test_call_itm_intrinsic(self):
        """ITM call has positive intrinsic value."""
        view = FakeView(
            balances={},
            states={
                "OPT": {
                    "strike": Decimal("150.0"),
                    "option_type": "call",
                    "quantity": Decimal("100"),
                    "long_wallet": "alice",
                }
            }
        )

        # spot=170, strike=Decimal("150"), quantity=Decimal("100") → (170-150)*100 = 2000
        value = get_option_intrinsic_value(view, "OPT", 170.0)
        assert value == Decimal("2000.0")

    def test_call_otm_intrinsic(self):
        """OTM call has zero intrinsic value."""
        view = FakeView(
            balances={},
            states={
                "OPT": {
                    "strike": Decimal("150.0"),
                    "option_type": "call",
                    "quantity": Decimal("100"),
                    "long_wallet": "alice",
                }
            }
        )

        value = get_option_intrinsic_value(view, "OPT", 140.0)
        assert value == Decimal("0.0")

    def test_put_itm_intrinsic(self):
        """ITM put has positive intrinsic value."""
        view = FakeView(
            balances={},
            states={
                "OPT": {
                    "strike": Decimal("150.0"),
                    "option_type": "put",
                    "quantity": Decimal("100"),
                    "long_wallet": "alice",
                }
            }
        )

        # spot=140, strike=Decimal("150"), quantity=Decimal("100") → (150-140)*100 = 1000
        value = get_option_intrinsic_value(view, "OPT", 140.0)
        assert value == Decimal("1000.0")


# =============================================================================
# FORWARDS
# =============================================================================

class TestCreateForwardUnit:
    """Tests for create_forward_unit factory."""

    def test_create_forward(self):
        """Create forward contract."""
        unit = create_forward_unit(
            symbol="AAPL_FWD",
            name="AAPL Forward",
            underlying="AAPL",
            forward_price=Decimal("160.0"),
            delivery_date=datetime(2025, 6, 20),
            quantity=Decimal("100"),
            currency="USD",
            long_wallet="alice",
            short_wallet="bob",
        )
        assert unit.symbol == "AAPL_FWD"
        assert unit.unit_type == "BILATERAL_FORWARD"
        assert unit.state['forward_price'] == 160.0

    def test_forward_has_bilateral_rule(self):
        """Forward has bilateral transfer rule."""
        unit = create_forward_unit(
            symbol="FWD",
            name="Test Forward",
            underlying="AAPL",
            forward_price=Decimal("160.0"),
            delivery_date=datetime(2025, 6, 20),
            quantity=Decimal("100"),
            currency="USD",
            long_wallet="alice",
            short_wallet="bob",
        )
        assert unit.transfer_rule is not None


class TestComputeForwardSettlement:
    """Tests for compute_forward_settlement pure function."""

    def test_forward_delivery(self):
        """Forward settles at delivery date."""
        view = FakeView(
            balances={
                "alice": {"FWD": Decimal("5"), "USD": Decimal("100000")},
                "bob": {"FWD": -5, "AAPL": Decimal("1000")},
            },
            states={
                "FWD": {
                    "unit_type": "BILATERAL_FORWARD",
                    "underlying": "AAPL",
                    "forward_price": Decimal("160.0"),
                    "delivery_date": datetime(2025, 6, 20),
                    "quantity": Decimal("100"),
                    "currency": "USD",
                    "long_wallet": "alice",
                    "short_wallet": "bob",
                    "settled": False,
                }
            },
            time=datetime(2025, 6, 20)
        )

        # At delivery date, settlement should execute
        result = compute_forward_settlement(view, "FWD")

        assert not result.is_empty()
        sc = next(d for d in result.state_changes if d.unit == "FWD")
        assert sc.new_state["settled"] is True

    def test_forward_before_delivery_empty(self):
        """Forward before delivery returns empty."""
        view = FakeView(
            balances={
                "alice": {"FWD": Decimal("5")},
                "bob": {"FWD": -5},
            },
            states={
                "FWD": {
                    "unit_type": "BILATERAL_FORWARD",
                    "underlying": "AAPL",
                    "forward_price": Decimal("160.0"),
                    "delivery_date": datetime(2025, 6, 20),
                    "quantity": Decimal("100"),
                    "currency": "USD",
                    "long_wallet": "alice",
                    "short_wallet": "bob",
                    "settled": False,
                }
            },
            time=datetime(2025, 6, 19)
        )

        # Before delivery date, settlement should return empty (no force_settlement)
        result = compute_forward_settlement(view, "FWD")
        assert result.is_empty()


class TestGetForwardValue:
    """Tests for get_forward_value."""

    def test_forward_profit(self):
        """Forward profit when spot > forward_price."""
        view = FakeView(
            balances={},
            states={
                "FWD": {
                    "forward_price": Decimal("160.0"),
                    "quantity": Decimal("100"),
                    "long_wallet": "alice",
                }
            }
        )

        # spot=170, forward=160, quantity=Decimal("100") → (170-160)*100 = 1000
        value = get_forward_value(view, "FWD", 170.0)
        assert value == Decimal("1000.0")

    def test_forward_loss(self):
        """Forward loss when spot < forward_price."""
        view = FakeView(
            balances={},
            states={
                "FWD": {
                    "forward_price": Decimal("160.0"),
                    "quantity": Decimal("100"),
                    "long_wallet": "alice",
                }
            }
        )

        # spot=150, forward=160, quantity=Decimal("100") → (150-160)*100 = -1000
        value = get_forward_value(view, "FWD", 150.0)
        assert value == Decimal("-1000.0")


# =============================================================================
# DELTA HEDGE
# =============================================================================

class TestCreateDeltaHedgeUnit:
    """Tests for create_delta_hedge_unit factory."""

    def test_create_delta_hedge(self):
        """Create delta hedge strategy."""
        unit = create_delta_hedge_unit(
            symbol="HEDGE",
            name="Test Hedge",
            underlying="AAPL",
            strike=Decimal("150.0"),
            maturity=datetime(2025, 6, 20),
            volatility=Decimal("0.25"),
            num_options=Decimal("10"),
            option_multiplier=Decimal("100"),
            currency="USD",
            strategy_wallet="trader",
            market_wallet="market",
            risk_free_rate=Decimal("0.0"),
        )
        assert unit.symbol == "HEDGE"
        assert unit.unit_type == "DELTA_HEDGE_STRATEGY"
        assert unit.state['underlying'] == "AAPL"
        assert unit.state['strike'] == 150.0


class TestComputeRebalance:
    """Tests for compute_rebalance pure function."""

    def test_rebalance_initial(self):
        """Initial rebalance buys shares."""
        view = FakeView(
            balances={
                "trader": {"USD": Decimal("500000")},
                "market": {"AAPL": Decimal("100000"), "USD": Decimal("10000000")},
            },
            states={
                "HEDGE": {
                    "unit_type": "DELTA_HEDGE_STRATEGY",
                    "underlying": "AAPL",
                    "strike": Decimal("150.0"),
                    "maturity": datetime(2025, 6, 20),
                    "volatility": Decimal("0.25"),
                    "num_options": Decimal("10"),
                    "option_multiplier": Decimal("100"),
                    "currency": "USD",
                    "strategy_wallet": "trader",
                    "market_wallet": "market",
                    "risk_free_rate": Decimal("0.0"),
                    "current_shares": Decimal("0.0"),
                    "rebalance_count": Decimal("0"),
                    "cumulative_cash": Decimal("0.0"),
                    "liquidated": False,
                }
            },
            time=datetime(2025, 1, 1)
        )

        result = compute_rebalance(view, "HEDGE", 150.0, min_trade_size=0.01)

        # Should buy some shares
        assert not result.is_empty()
        # Should have moves for cash and shares
        assert len(result.moves) == 2

    def test_rebalance_at_maturity_empty(self):
        """Rebalance at maturity returns empty."""
        view = FakeView(
            balances={
                "trader": {"USD": Decimal("500000"), "AAPL": Decimal("500")},
                "market": {"AAPL": Decimal("100000"), "USD": Decimal("10000000")},
            },
            states={
                "HEDGE": {
                    "unit_type": "DELTA_HEDGE_STRATEGY",
                    "underlying": "AAPL",
                    "strike": Decimal("150.0"),
                    "maturity": datetime(2025, 6, 20),
                    "volatility": Decimal("0.25"),
                    "num_options": Decimal("10"),
                    "option_multiplier": Decimal("100"),
                    "currency": "USD",
                    "strategy_wallet": "trader",
                    "market_wallet": "market",
                    "risk_free_rate": Decimal("0.0"),
                    "current_shares": Decimal("500.0"),
                    "rebalance_count": Decimal("10"),
                    "cumulative_cash": -75000.0,
                    "liquidated": False,
                }
            },
            time=datetime(2025, 6, 20)  # At maturity
        )

        result = compute_rebalance(view, "HEDGE", 150.0, min_trade_size=0.01)
        assert result.is_empty()

    def test_rebalance_liquidated_empty(self):
        """Rebalance when liquidated returns empty."""
        view = FakeView(
            balances={
                "trader": {"USD": Decimal("500000")},
                "market": {"AAPL": Decimal("100000"), "USD": Decimal("10000000")},
            },
            states={
                "HEDGE": {
                    "unit_type": "DELTA_HEDGE_STRATEGY",
                    "underlying": "AAPL",
                    "strike": Decimal("150.0"),
                    "maturity": datetime(2025, 6, 20),
                    "volatility": Decimal("0.25"),
                    "num_options": Decimal("10"),
                    "option_multiplier": Decimal("100"),
                    "currency": "USD",
                    "strategy_wallet": "trader",
                    "market_wallet": "market",
                    "risk_free_rate": Decimal("0.0"),
                    "current_shares": Decimal("0.0"),
                    "rebalance_count": Decimal("10"),
                    "cumulative_cash": -75000.0,
                    "liquidated": True,  # Already liquidated
                }
            },
            time=datetime(2025, 4, 1)
        )

        result = compute_rebalance(view, "HEDGE", 150.0, min_trade_size=0.01)
        assert result.is_empty()


class TestComputeLiquidation:
    """Tests for compute_liquidation pure function."""

    def test_liquidation_sells_shares(self):
        """Liquidation sells all shares."""
        view = FakeView(
            balances={
                "trader": {"USD": Decimal("400000"), "AAPL": Decimal("500")},
                "market": {"AAPL": Decimal("100000"), "USD": Decimal("10000000")},
            },
            states={
                "HEDGE": {
                    "unit_type": "DELTA_HEDGE_STRATEGY",
                    "underlying": "AAPL",
                    "strike": Decimal("150.0"),
                    "maturity": datetime(2025, 6, 20),
                    "volatility": Decimal("0.25"),
                    "num_options": Decimal("10"),
                    "option_multiplier": Decimal("100"),
                    "currency": "USD",
                    "strategy_wallet": "trader",
                    "market_wallet": "market",
                    "risk_free_rate": Decimal("0.0"),
                    "current_shares": Decimal("500.0"),
                    "rebalance_count": Decimal("10"),
                    "cumulative_cash": -75000.0,
                    "liquidated": False,
                }
            },
            time=datetime(2025, 6, 20)
        )

        result = compute_liquidation(view, "HEDGE", 160.0)

        assert not result.is_empty()
        sc = next(d for d in result.state_changes if d.unit == "HEDGE")
        assert sc.new_state["liquidated"] is True
        assert sc.new_state["current_shares"] == 0.0

    def test_liquidation_already_liquidated_empty(self):
        """Liquidation when already liquidated returns empty."""
        view = FakeView(
            balances={
                "trader": {"USD": Decimal("500000")},
                "market": {"AAPL": Decimal("100000"), "USD": Decimal("10000000")},
            },
            states={
                "HEDGE": {
                    "unit_type": "DELTA_HEDGE_STRATEGY",
                    "underlying": "AAPL",
                    "strike": Decimal("150.0"),
                    "maturity": datetime(2025, 6, 20),
                    "volatility": Decimal("0.25"),
                    "num_options": Decimal("10"),
                    "option_multiplier": Decimal("100"),
                    "currency": "USD",
                    "strategy_wallet": "trader",
                    "market_wallet": "market",
                    "risk_free_rate": Decimal("0.0"),
                    "current_shares": Decimal("0.0"),
                    "rebalance_count": Decimal("10"),
                    "cumulative_cash": -75000.0,
                    "liquidated": True,
                }
            },
            time=datetime(2025, 6, 20)
        )

        result = compute_liquidation(view, "HEDGE", 160.0)
        assert result.is_empty()


class TestGetHedgeState:
    """Tests for get_hedge_state."""

    def test_get_hedge_state_all_fields(self):
        """get_hedge_state returns all relevant fields."""
        view = FakeView(
            balances={
                "trader": {"AAPL": Decimal("500")},
            },
            states={
                "HEDGE": {
                    "unit_type": "DELTA_HEDGE_STRATEGY",
                    "underlying": "AAPL",
                    "strike": Decimal("150.0"),
                    "maturity": datetime(2025, 6, 20),
                    "volatility": Decimal("0.25"),
                    "num_options": Decimal("10"),
                    "option_multiplier": Decimal("100"),
                    "currency": "USD",
                    "strategy_wallet": "trader",
                    "market_wallet": "market",
                    "risk_free_rate": Decimal("0.0"),
                    "current_shares": Decimal("500.0"),
                    "rebalance_count": Decimal("10"),
                    "cumulative_cash": -75000.0,
                    "liquidated": False,
                }
            },
            time=datetime(2025, 4, 1)
        )

        state = get_hedge_state(view, "HEDGE", 160.0)

        assert "delta" in state
        assert "current_shares" in state
        assert "cumulative_cash" in state
        assert "liquidated" in state


class TestDeltaHedgeContract:
    """Tests for delta_hedge_contract SmartContract factory."""

    def test_delta_hedge_contract_factory(self):
        """delta_hedge_contract returns callable."""
        contract = delta_hedge_contract(min_trade_size=0.01)
        assert callable(contract)

    def test_delta_hedge_contract_returns_result(self):
        """Contract call returns ."""
        view = FakeView(
            balances={
                "trader": {"USD": Decimal("500000")},
                "market": {"AAPL": Decimal("100000"), "USD": Decimal("10000000")},
            },
            states={
                "HEDGE": {
                    "unit_type": "DELTA_HEDGE_STRATEGY",
                    "underlying": "AAPL",
                    "strike": Decimal("150.0"),
                    "maturity": datetime(2025, 6, 20),
                    "volatility": Decimal("0.25"),
                    "num_options": Decimal("10"),
                    "option_multiplier": Decimal("100"),
                    "currency": "USD",
                    "strategy_wallet": "trader",
                    "market_wallet": "market",
                    "risk_free_rate": Decimal("0.0"),
                    "current_shares": Decimal("0.0"),
                    "rebalance_count": Decimal("0"),
                    "cumulative_cash": Decimal("0.0"),
                    "liquidated": False,
                }
            },
            time=datetime(2025, 1, 1)
        )

        contract = delta_hedge_contract(min_trade_size=0.01)
        result = contract(view, "HEDGE", datetime(2025, 1, 1), {"AAPL": Decimal("150.0")})

        assert isinstance(result, PendingTransaction)
