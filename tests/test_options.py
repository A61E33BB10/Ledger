"""
test_options.py - Unit tests for options.py

Tests:
- create_option_unit: unit creation (creates bilateral option units)
- build_option_trade: trade building (generates contract results for option trades)
- compute_option_settlement: ITM/OTM call/put settlement (settles options at maturity)
- Convenience functions: get_option_intrinsic_value, get_option_moneyness
- option_contract: SmartContract implementation (automated settlement)
"""

import pytest
from datetime import datetime
from ledger import (
    Move, ContractResult, Unit,
    create_option_unit, build_option_trade,
    compute_option_settlement,
    get_option_intrinsic_value, get_option_moneyness,
    option_contract,
)
from .fake_view import FakeView


class TestCreateOptionUnit:
    """Tests for create_option_unit factory."""

    def test_create_call_option_unit(self):
        unit = create_option_unit(
            symbol="AAPL_C150_DEC25",
            name="AAPL Call 150 Dec25",
            underlying="AAPL",
            strike=150.0,
            maturity=datetime(2025, 12, 19),
            option_type="call",
            quantity=100,
            currency="USD",
            long_wallet="alice",
            short_wallet="bob"
        )

        assert unit.symbol == "AAPL_C150_DEC25"
        assert unit.name == "AAPL Call 150 Dec25"
        assert unit.unit_type == "BILATERAL_OPTION"
        assert unit._state['underlying'] == "AAPL"
        assert unit._state['strike'] == 150.0
        assert unit._state['option_type'] == "call"
        assert unit._state['settled'] is False

    def test_create_put_option_unit(self):
        unit = create_option_unit(
            symbol="AAPL_P140_DEC25",
            name="AAPL Put 140 Dec25",
            underlying="AAPL",
            strike=140.0,
            maturity=datetime(2025, 12, 19),
            option_type="put",
            quantity=100,
            currency="USD",
            long_wallet="alice",
            short_wallet="bob"
        )

        assert unit._state['option_type'] == "put"
        assert unit._state['strike'] == 140.0

    def test_create_option_unit_validates_type(self):
        """Invalid option type should raise."""
        with pytest.raises(ValueError, match="option_type must be"):
            create_option_unit(
                symbol="TEST",
                name="Test Option",
                underlying="AAPL",
                strike=150.0,
                maturity=datetime(2025, 12, 19),
                option_type="invalid",
                quantity=100,
                currency="USD",
                long_wallet="alice",
                short_wallet="bob"
            )

    def test_create_option_unit_validates_strike(self):
        """Non-positive strike should raise."""
        with pytest.raises(ValueError, match="strike must be positive"):
            create_option_unit(
                symbol="TEST",
                name="Test Option",
                underlying="AAPL",
                strike=0.0,
                maturity=datetime(2025, 12, 19),
                option_type="call",
                quantity=100,
                currency="USD",
                long_wallet="alice",
                short_wallet="bob"
            )

    def test_create_option_unit_validates_quantity(self):
        """Non-positive quantity should raise."""
        with pytest.raises(ValueError, match="quantity must be positive"):
            create_option_unit(
                symbol="TEST",
                name="Test Option",
                underlying="AAPL",
                strike=150.0,
                maturity=datetime(2025, 12, 19),
                option_type="call",
                quantity=-10,
                currency="USD",
                long_wallet="alice",
                short_wallet="bob"
            )


class TestBuildOptionTrade:
    """Tests for build_option_trade function."""

    def test_build_trade_returns_contract_result(self):
        result = build_option_trade(
            option_symbol="AAPL_C150",
            num_contracts=5,
            premium_per_contract=8.50,
            buyer="alice",
            seller="bob",
            premium_currency="USD",
            trade_id="trade_001"
        )
        assert isinstance(result, ContractResult)
        assert len(result.moves) == 2

    def test_build_trade_premium_move(self):
        result = build_option_trade(
            option_symbol="AAPL_C150",
            num_contracts=10,
            premium_per_contract=5.0,
            buyer="alice",
            seller="bob",
            premium_currency="USD",
            trade_id="trade_001"
        )
        premium_move = result.moves[0]
        assert premium_move.source == "alice"
        assert premium_move.dest == "bob"
        assert premium_move.unit == "USD"
        assert premium_move.quantity == 50.0  # 10 * 5.0

    def test_build_trade_option_move(self):
        result = build_option_trade(
            option_symbol="AAPL_C150",
            num_contracts=10,
            premium_per_contract=5.0,
            buyer="alice",
            seller="bob",
            premium_currency="USD",
            trade_id="trade_001"
        )
        option_move = result.moves[1]
        assert option_move.source == "bob"
        assert option_move.dest == "alice"
        assert option_move.unit == "AAPL_C150"
        assert option_move.quantity == 10


class TestComputeOptionSettlement:
    """Tests for compute_option_settlement function."""

    def test_call_itm_settlement(self):
        """Call ITM: long pays strike, receives underlying."""
        view = FakeView(
            balances={
                'alice': {'OPT': 5, 'USD': 100000},
                'bob': {'OPT': -5, 'AAPL': 1000},
            },
            states={
                'OPT': {
                    'underlying': 'AAPL',
                    'strike': 100.0,
                    'maturity': datetime(2025, 6, 1),
                    'option_type': 'call',
                    'quantity': 100,
                    'currency': 'USD',
                    'long_wallet': 'alice',
                    'short_wallet': 'bob',
                    'settled': False,
                }
            },
            time=datetime(2025, 6, 1)
        )
        result = compute_option_settlement(view, 'OPT', settlement_price=120.0)

        assert not result.is_empty()
        # Should have 3 moves: cash, delivery, close position
        assert len(result.moves) == 3

        # Check cash move (long pays strike * quantity)
        cash_move = next(m for m in result.moves if m.unit == 'USD')
        assert cash_move.source == 'alice'
        assert cash_move.dest == 'bob'
        assert cash_move.quantity == 5 * 100 * 100.0  # 5 contracts * 100 shares * $100

        # Check delivery move
        delivery_move = next(m for m in result.moves if m.unit == 'AAPL')
        assert delivery_move.source == 'bob'
        assert delivery_move.dest == 'alice'
        assert delivery_move.quantity == 5 * 100  # 5 contracts * 100 shares

        # Check state updates
        assert result.state_updates['OPT']['settled'] is True
        assert result.state_updates['OPT']['exercised'] is True

    def test_call_otm_settlement(self):
        """Call OTM: just close positions, no physical delivery."""
        view = FakeView(
            balances={
                'alice': {'OPT': 5},
                'bob': {'OPT': -5},
            },
            states={
                'OPT': {
                    'underlying': 'AAPL',
                    'strike': 150.0,
                    'maturity': datetime(2025, 6, 1),
                    'option_type': 'call',
                    'quantity': 100,
                    'currency': 'USD',
                    'long_wallet': 'alice',
                    'short_wallet': 'bob',
                    'settled': False,
                }
            },
            time=datetime(2025, 6, 1)
        )
        result = compute_option_settlement(view, 'OPT', settlement_price=100.0)

        assert not result.is_empty()
        # OTM: only close position move
        assert len(result.moves) == 1
        close_move = result.moves[0]
        assert close_move.unit == 'OPT'
        assert result.state_updates['OPT']['exercised'] is False

    def test_put_itm_settlement(self):
        """Put ITM: long delivers underlying, receives cash."""
        view = FakeView(
            balances={
                'alice': {'OPT': 3, 'AAPL': 500},
                'bob': {'OPT': -3, 'USD': 100000},
            },
            states={
                'OPT': {
                    'underlying': 'AAPL',
                    'strike': 100.0,
                    'maturity': datetime(2025, 6, 1),
                    'option_type': 'put',
                    'quantity': 100,
                    'currency': 'USD',
                    'long_wallet': 'alice',
                    'short_wallet': 'bob',
                    'settled': False,
                }
            },
            time=datetime(2025, 6, 1)
        )
        result = compute_option_settlement(view, 'OPT', settlement_price=80.0)

        assert not result.is_empty()
        assert len(result.moves) == 3

        # Check delivery move (long delivers underlying)
        delivery_move = next(m for m in result.moves if m.unit == 'AAPL')
        assert delivery_move.source == 'alice'
        assert delivery_move.dest == 'bob'

        # Check cash move (short pays long)
        cash_move = next(m for m in result.moves if m.unit == 'USD')
        assert cash_move.source == 'bob'
        assert cash_move.dest == 'alice'

    def test_settlement_before_maturity_returns_empty(self):
        view = FakeView(
            balances={'alice': {'OPT': 5}, 'bob': {'OPT': -5}},
            states={
                'OPT': {
                    'underlying': 'AAPL',
                    'strike': 100.0,
                    'maturity': datetime(2025, 12, 31),
                    'option_type': 'call',
                    'quantity': 100,
                    'currency': 'USD',
                    'long_wallet': 'alice',
                    'short_wallet': 'bob',
                    'settled': False,
                }
            },
            time=datetime(2025, 6, 1)
        )
        result = compute_option_settlement(view, 'OPT', settlement_price=150.0)
        assert result.is_empty()

    def test_force_settlement_before_maturity(self):
        view = FakeView(
            balances={'alice': {'OPT': 5, 'USD': 100000}, 'bob': {'OPT': -5, 'AAPL': 1000}},
            states={
                'OPT': {
                    'underlying': 'AAPL',
                    'strike': 100.0,
                    'maturity': datetime(2025, 12, 31),
                    'option_type': 'call',
                    'quantity': 100,
                    'currency': 'USD',
                    'long_wallet': 'alice',
                    'short_wallet': 'bob',
                    'settled': False,
                }
            },
            time=datetime(2025, 6, 1)
        )
        result = compute_option_settlement(view, 'OPT', settlement_price=150.0, force_settlement=True)
        assert not result.is_empty()

    def test_already_settled_returns_empty(self):
        view = FakeView(
            balances={'alice': {'OPT': 0}, 'bob': {'OPT': 0}},
            states={
                'OPT': {
                    'underlying': 'AAPL',
                    'strike': 100.0,
                    'maturity': datetime(2025, 6, 1),
                    'option_type': 'call',
                    'quantity': 100,
                    'currency': 'USD',
                    'long_wallet': 'alice',
                    'short_wallet': 'bob',
                    'settled': True,
                }
            },
            time=datetime(2025, 6, 1)
        )
        result = compute_option_settlement(view, 'OPT', settlement_price=150.0)
        assert result.is_empty()


class TestOptionConvenienceFunctions:
    """Tests for option convenience functions."""

    def test_get_option_intrinsic_value_call_itm(self):
        view = FakeView(
            balances={},
            states={
                'OPT': {
                    'underlying': 'AAPL',
                    'strike': 100.0,
                    'maturity': datetime(2025, 12, 31),
                    'option_type': 'call',
                    'quantity': 100,
                    'currency': 'USD',
                    'long_wallet': 'alice',
                    'short_wallet': 'bob',
                }
            }
        )
        value = get_option_intrinsic_value(view, 'OPT', spot_price=120.0)
        assert value == 20.0 * 100  # (120 - 100) * 100 shares

    def test_get_option_intrinsic_value_call_otm(self):
        view = FakeView(
            balances={},
            states={
                'OPT': {
                    'underlying': 'AAPL',
                    'strike': 100.0,
                    'maturity': datetime(2025, 12, 31),
                    'option_type': 'call',
                    'quantity': 100,
                    'currency': 'USD',
                    'long_wallet': 'alice',
                    'short_wallet': 'bob',
                }
            }
        )
        value = get_option_intrinsic_value(view, 'OPT', spot_price=80.0)
        assert value == 0.0

    def test_get_option_intrinsic_value_put_itm(self):
        view = FakeView(
            balances={},
            states={
                'OPT': {
                    'underlying': 'AAPL',
                    'strike': 100.0,
                    'maturity': datetime(2025, 12, 31),
                    'option_type': 'put',
                    'quantity': 100,
                    'currency': 'USD',
                    'long_wallet': 'alice',
                    'short_wallet': 'bob',
                }
            }
        )
        value = get_option_intrinsic_value(view, 'OPT', spot_price=80.0)
        assert value == 20.0 * 100  # (100 - 80) * 100 shares

    def test_get_option_moneyness_itm_call(self):
        view = FakeView(
            balances={},
            states={
                'OPT': {
                    'underlying': 'AAPL',
                    'strike': 100.0,
                    'maturity': datetime(2025, 12, 31),
                    'option_type': 'call',
                    'quantity': 100,
                    'currency': 'USD',
                    'long_wallet': 'alice',
                    'short_wallet': 'bob',
                }
            }
        )
        assert get_option_moneyness(view, 'OPT', 120.0) == 'ITM'

    def test_get_option_moneyness_otm_call(self):
        view = FakeView(
            balances={},
            states={
                'OPT': {
                    'underlying': 'AAPL',
                    'strike': 100.0,
                    'maturity': datetime(2025, 12, 31),
                    'option_type': 'call',
                    'quantity': 100,
                    'currency': 'USD',
                    'long_wallet': 'alice',
                    'short_wallet': 'bob',
                }
            }
        )
        assert get_option_moneyness(view, 'OPT', 80.0) == 'OTM'

    def test_get_option_moneyness_atm(self):
        view = FakeView(
            balances={},
            states={
                'OPT': {
                    'underlying': 'AAPL',
                    'strike': 100.0,
                    'maturity': datetime(2025, 12, 31),
                    'option_type': 'call',
                    'quantity': 100,
                    'currency': 'USD',
                    'long_wallet': 'alice',
                    'short_wallet': 'bob',
                }
            }
        )
        assert get_option_moneyness(view, 'OPT', 100.5) == 'ATM'

class TestOptionContract:
    """Tests for option_contract SmartContract implementation."""

    def test_check_lifecycle_not_matured(self):
        view = FakeView(
            balances={'alice': {'OPT': 5}, 'bob': {'OPT': -5}},
            states={
                'OPT': {
                    'underlying': 'AAPL',
                    'strike': 100.0,
                    'maturity': datetime(2025, 12, 31),
                    'option_type': 'call',
                    'quantity': 100,
                    'currency': 'USD',
                    'long_wallet': 'alice',
                    'short_wallet': 'bob',
                    'settled': False,
                }
            },
            time=datetime(2025, 6, 1)
        )
        result = option_contract(view, 'OPT', datetime(2025, 6, 1), {'AAPL': 150.0})
        assert result.is_empty()

    def test_check_lifecycle_at_maturity(self):
        view = FakeView(
            balances={
                'alice': {'OPT': 5, 'USD': 100000},
                'bob': {'OPT': -5, 'AAPL': 1000},
            },
            states={
                'OPT': {
                    'underlying': 'AAPL',
                    'strike': 100.0,
                    'maturity': datetime(2025, 6, 1),
                    'option_type': 'call',
                    'quantity': 100,
                    'currency': 'USD',
                    'long_wallet': 'alice',
                    'short_wallet': 'bob',
                    'settled': False,
                }
            },
            time=datetime(2025, 6, 1)
        )
        result = option_contract(view, 'OPT', datetime(2025, 6, 1), {'AAPL': 150.0})
        assert not result.is_empty()

    def test_check_lifecycle_already_settled(self):
        view = FakeView(
            balances={'alice': {}, 'bob': {}},
            states={
                'OPT': {
                    'underlying': 'AAPL',
                    'strike': 100.0,
                    'maturity': datetime(2025, 6, 1),
                    'option_type': 'call',
                    'quantity': 100,
                    'currency': 'USD',
                    'long_wallet': 'alice',
                    'short_wallet': 'bob',
                    'settled': True,
                }
            },
            time=datetime(2025, 6, 1)
        )
        result = option_contract(view, 'OPT', datetime(2025, 6, 1), {'AAPL': 150.0})
        assert result.is_empty()

    def test_check_lifecycle_missing_price(self):
        view = FakeView(
            balances={'alice': {'OPT': 5}, 'bob': {'OPT': -5}},
            states={
                'OPT': {
                    'underlying': 'AAPL',
                    'strike': 100.0,
                    'maturity': datetime(2025, 6, 1),
                    'option_type': 'call',
                    'quantity': 100,
                    'currency': 'USD',
                    'long_wallet': 'alice',
                    'short_wallet': 'bob',
                    'settled': False,
                }
            },
            time=datetime(2025, 6, 1)
        )
        # No AAPL price provided
        result = option_contract(view, 'OPT', datetime(2025, 6, 1), {'TSLA': 200.0})
        assert result.is_empty()
