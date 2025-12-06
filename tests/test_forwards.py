"""
test_forwards.py - Unit tests for forwards.py

Tests:
- create_forward_unit: unit creation (creates bilateral forward contracts)
- compute_forward_settlement: settlement at delivery date (physical delivery)
- Convenience functions: get_forward_value (computes mark-to-market value)
- forward_contract: SmartContract implementation (automated settlement)
"""

import pytest
from datetime import datetime
from ledger import (
    Move, ContractResult, Unit,
    create_forward_unit,
    compute_forward_settlement,
    get_forward_value,
    forward_contract,
)
from .fake_view import FakeView


class TestCreateForwardUnit:
    """Tests for create_forward_unit factory."""

    def test_create_forward_unit(self):
        unit = create_forward_unit(
            symbol="OIL_FWD_JUN25",
            name="Oil Forward Jun25",
            underlying="OIL",
            forward_price=75.0,
            delivery_date=datetime(2025, 6, 1),
            quantity=1000,
            currency="USD",
            long_wallet="alice",
            short_wallet="bob"
        )

        assert unit.symbol == "OIL_FWD_JUN25"
        assert unit.name == "Oil Forward Jun25"
        assert unit.unit_type == "BILATERAL_FORWARD"
        assert unit._state['underlying'] == "OIL"
        assert unit._state['forward_price'] == 75.0
        assert unit._state['quantity'] == 1000
        assert unit._state['settled'] is False

    def test_create_forward_unit_validates_price(self):
        """Non-positive forward price should raise."""
        with pytest.raises(ValueError, match="forward_price must be positive"):
            create_forward_unit(
                symbol="TEST",
                name="Test Forward",
                underlying="OIL",
                forward_price=0.0,
                delivery_date=datetime(2025, 6, 1),
                quantity=1000,
                currency="USD",
                long_wallet="alice",
                short_wallet="bob"
            )

    def test_create_forward_unit_validates_negative_price(self):
        """Negative forward price should raise."""
        with pytest.raises(ValueError, match="forward_price must be positive"):
            create_forward_unit(
                symbol="TEST",
                name="Test Forward",
                underlying="OIL",
                forward_price=-10.0,
                delivery_date=datetime(2025, 6, 1),
                quantity=1000,
                currency="USD",
                long_wallet="alice",
                short_wallet="bob"
            )

    def test_create_forward_unit_validates_quantity(self):
        """Non-positive quantity should raise."""
        with pytest.raises(ValueError, match="quantity must be positive"):
            create_forward_unit(
                symbol="TEST",
                name="Test Forward",
                underlying="OIL",
                forward_price=75.0,
                delivery_date=datetime(2025, 6, 1),
                quantity=-100,
                currency="USD",
                long_wallet="alice",
                short_wallet="bob"
            )

    def test_forward_unit_has_bilateral_transfer_rule(self):
        unit = create_forward_unit(
            symbol="GBP_FWD",
            name="GBP Forward",
            underlying="GBP",
            forward_price=1.25,
            delivery_date=datetime(2025, 6, 1),
            quantity=10000,
            currency="USD",
            long_wallet="alice",
            short_wallet="bob"
        )
        assert unit.transfer_rule is not None


class TestComputeForwardSettlement:
    """Tests for compute_forward_settlement function."""

    def test_forward_settlement_at_delivery(self):
        """Forward settlement: long pays cash, receives underlying."""
        view = FakeView(
            balances={
                'alice': {'FWD': 2, 'USD': 200000},
                'bob': {'FWD': -2, 'OIL': 5000},
            },
            states={
                'FWD': {
                    'underlying': 'OIL',
                    'forward_price': 75.0,
                    'delivery_date': datetime(2025, 6, 1),
                    'quantity': 1000,
                    'currency': 'USD',
                    'long_wallet': 'alice',
                    'short_wallet': 'bob',
                    'settled': False,
                }
            },
            time=datetime(2025, 6, 1)
        )
        result = compute_forward_settlement(view, 'FWD')

        assert not result.is_empty()
        assert len(result.moves) == 3  # cash, delivery, close

        # Check cash move
        cash_move = next(m for m in result.moves if m.unit == 'USD')
        assert cash_move.source == 'alice'
        assert cash_move.dest == 'bob'
        # 2 contracts * 1000 qty * $75 = $150,000
        assert cash_move.quantity == 2 * 1000 * 75.0

        # Check delivery move
        delivery_move = next(m for m in result.moves if m.unit == 'OIL')
        assert delivery_move.source == 'bob'
        assert delivery_move.dest == 'alice'
        assert delivery_move.quantity == 2 * 1000

        # Check close position
        close_move = next(m for m in result.moves if m.unit == 'FWD')
        assert close_move.source == 'alice'
        assert close_move.dest == 'bob'
        assert close_move.quantity == 2

        # Check state updates
        assert result.state_updates['FWD']['settled'] is True

    def test_settlement_before_delivery_returns_empty(self):
        view = FakeView(
            balances={'alice': {'FWD': 2}, 'bob': {'FWD': -2}},
            states={
                'FWD': {
                    'underlying': 'OIL',
                    'forward_price': 75.0,
                    'delivery_date': datetime(2025, 12, 31),
                    'quantity': 1000,
                    'currency': 'USD',
                    'long_wallet': 'alice',
                    'short_wallet': 'bob',
                    'settled': False,
                }
            },
            time=datetime(2025, 6, 1)
        )
        result = compute_forward_settlement(view, 'FWD')
        assert result.is_empty()

    def test_force_settlement_before_delivery(self):
        view = FakeView(
            balances={
                'alice': {'FWD': 1, 'USD': 100000},
                'bob': {'FWD': -1, 'OIL': 2000},
            },
            states={
                'FWD': {
                    'underlying': 'OIL',
                    'forward_price': 75.0,
                    'delivery_date': datetime(2025, 12, 31),
                    'quantity': 1000,
                    'currency': 'USD',
                    'long_wallet': 'alice',
                    'short_wallet': 'bob',
                    'settled': False,
                }
            },
            time=datetime(2025, 6, 1)
        )
        result = compute_forward_settlement(view, 'FWD', force_settlement=True)
        assert not result.is_empty()
        assert result.state_updates['FWD']['settled'] is True

    def test_already_settled_returns_empty(self):
        view = FakeView(
            balances={'alice': {}, 'bob': {}},
            states={
                'FWD': {
                    'underlying': 'OIL',
                    'forward_price': 75.0,
                    'delivery_date': datetime(2025, 6, 1),
                    'quantity': 1000,
                    'currency': 'USD',
                    'long_wallet': 'alice',
                    'short_wallet': 'bob',
                    'settled': True,
                }
            },
            time=datetime(2025, 6, 1)
        )
        result = compute_forward_settlement(view, 'FWD')
        assert result.is_empty()

    def test_no_position_returns_empty(self):
        view = FakeView(
            balances={'alice': {'FWD': 0}, 'bob': {'FWD': 0}},
            states={
                'FWD': {
                    'underlying': 'OIL',
                    'forward_price': 75.0,
                    'delivery_date': datetime(2025, 6, 1),
                    'quantity': 1000,
                    'currency': 'USD',
                    'long_wallet': 'alice',
                    'short_wallet': 'bob',
                    'settled': False,
                }
            },
            time=datetime(2025, 6, 1)
        )
        result = compute_forward_settlement(view, 'FWD')
        assert result.is_empty()


class TestForwardConvenienceFunctions:
    """Tests for forward convenience functions."""

    def test_get_forward_value_profit(self):
        """Value to long when spot > forward_price."""
        view = FakeView(
            balances={},
            states={
                'FWD': {
                    'underlying': 'OIL',
                    'forward_price': 75.0,
                    'delivery_date': datetime(2025, 6, 1),
                    'quantity': 1000,
                    'currency': 'USD',
                    'long_wallet': 'alice',
                    'short_wallet': 'bob',
                }
            }
        )
        value = get_forward_value(view, 'FWD', spot_price=80.0)
        # (80 - 75) * 1000 = 5000
        assert value == 5000.0

    def test_get_forward_value_loss(self):
        """Value to long when spot < forward_price."""
        view = FakeView(
            balances={},
            states={
                'FWD': {
                    'underlying': 'OIL',
                    'forward_price': 75.0,
                    'delivery_date': datetime(2025, 6, 1),
                    'quantity': 1000,
                    'currency': 'USD',
                    'long_wallet': 'alice',
                    'short_wallet': 'bob',
                }
            }
        )
        value = get_forward_value(view, 'FWD', spot_price=70.0)
        # (70 - 75) * 1000 = -5000
        assert value == -5000.0

    def test_get_forward_value_breakeven(self):
        """Value to long when spot == forward_price."""
        view = FakeView(
            balances={},
            states={
                'FWD': {
                    'underlying': 'OIL',
                    'forward_price': 75.0,
                    'delivery_date': datetime(2025, 6, 1),
                    'quantity': 1000,
                    'currency': 'USD',
                    'long_wallet': 'alice',
                    'short_wallet': 'bob',
                }
            }
        )
        value = get_forward_value(view, 'FWD', spot_price=75.0)
        assert value == 0.0

class TestForwardContract:
    """Tests for forward_contract SmartContract implementation."""

    def test_check_lifecycle_not_matured(self):
        view = FakeView(
            balances={'alice': {'FWD': 2}, 'bob': {'FWD': -2}},
            states={
                'FWD': {
                    'underlying': 'OIL',
                    'forward_price': 75.0,
                    'delivery_date': datetime(2025, 12, 31),
                    'quantity': 1000,
                    'currency': 'USD',
                    'long_wallet': 'alice',
                    'short_wallet': 'bob',
                    'settled': False,
                }
            },
            time=datetime(2025, 6, 1)
        )
        result = forward_contract(view, 'FWD', datetime(2025, 6, 1), {'OIL': 80.0})
        assert result.is_empty()

    def test_check_lifecycle_at_delivery_date(self):
        view = FakeView(
            balances={
                'alice': {'FWD': 1, 'USD': 100000},
                'bob': {'FWD': -1, 'OIL': 2000},
            },
            states={
                'FWD': {
                    'underlying': 'OIL',
                    'forward_price': 75.0,
                    'delivery_date': datetime(2025, 6, 1),
                    'quantity': 1000,
                    'currency': 'USD',
                    'long_wallet': 'alice',
                    'short_wallet': 'bob',
                    'settled': False,
                }
            },
            time=datetime(2025, 6, 1)
        )
        result = forward_contract(view, 'FWD', datetime(2025, 6, 1), {'OIL': 80.0})
        assert not result.is_empty()

    def test_check_lifecycle_already_settled(self):
        view = FakeView(
            balances={'alice': {}, 'bob': {}},
            states={
                'FWD': {
                    'underlying': 'OIL',
                    'forward_price': 75.0,
                    'delivery_date': datetime(2025, 6, 1),
                    'quantity': 1000,
                    'currency': 'USD',
                    'long_wallet': 'alice',
                    'short_wallet': 'bob',
                    'settled': True,
                }
            },
            time=datetime(2025, 6, 1)
        )
        result = forward_contract(view, 'FWD', datetime(2025, 6, 1), {'OIL': 80.0})
        assert result.is_empty()

    def test_check_lifecycle_no_delivery_date(self):
        view = FakeView(
            balances={'alice': {'FWD': 1}, 'bob': {'FWD': -1}},
            states={
                'FWD': {
                    'settled': False,
                }
            },
            time=datetime(2025, 6, 1)
        )
        result = forward_contract(view, 'FWD', datetime(2025, 6, 1), {'OIL': 80.0})
        assert result.is_empty()
