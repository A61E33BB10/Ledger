"""
test_futures.py - Tests for simplified futures module

Tests the 3-function API:
- create_future(): factory
- transact(view, symbol, seller, buyer, qty, price): two-party trade via clearinghouse
- future_contract(): SmartContract for MTM and expiry

=== THE VIRTUAL CASH MODEL ===

Per-wallet state:
    virtual_cash: Sum of (-qty * price * mult) for all trades

On TRADE at price P:
    Buyer: virtual_cash -= qty * P * mult
    Seller: virtual_cash += qty * P * mult

On MTM at price P:
    target_vcash = -position * P * mult
    vm = virtual_cash - target_vcash
    virtual_cash = target_vcash

This is equivalent to: position * (P - avg_entry_price) * mult
"""

import pytest
from datetime import datetime
from decimal import Decimal
from tests.fake_view import FakeView
from ledger import create_future, future_transact, future_contract
from ledger.core import UNIT_TYPE_FUTURE


# ============================================================================
# CREATE FUTURE
# ============================================================================

class TestCreateFuture:
    def test_basic(self):
        f = create_future("ESZ24", "E-mini Dec 24", "SPX", datetime(2024, 12, 20), 50.0, "USD", "clearing")
        assert f.symbol == "ESZ24"
        assert f.unit_type == UNIT_TYPE_FUTURE
        assert f.state["multiplier"] == 50.0
        assert f.state["clearinghouse"] == "clearing"
        assert f.state["settled"] is False

    def test_invalid_multiplier(self):
        with pytest.raises(ValueError, match="multiplier must be positive"):
            create_future("X", "X", "X", datetime(2024, 12, 20), 0.0, "USD", "clearing")

    def test_empty_clearinghouse(self):
        with pytest.raises(ValueError, match="clearinghouse_id cannot be empty"):
            create_future("X", "X", "X", datetime(2024, 12, 20), 50.0, "USD", "")


# ============================================================================
# TRANSACT - TWO-PARTY TRADE VIA CLEARINGHOUSE
# ============================================================================

class TestTransact:
    def setup_method(self):
        self.state = {
            'underlying': 'SPX', 'expiry': datetime(2024, 12, 20), 'multiplier': Decimal("50.0"),
            'currency': 'USD', 'clearinghouse': 'clearing', 'wallets': {}, 'settled': False,
        }

    def test_buy_from_market_maker(self):
        """Trader buys from market_maker: market_maker sells to trader via clearinghouse"""
        # market_maker has position tracked in wallets state
        state = {**self.state, 'wallets': {'market_maker': {'position': Decimal("100"), 'virtual_cash': Decimal("0.0")}}}
        view = FakeView(
            balances={'trader': {}, 'market_maker': {'ESZ24': Decimal("100")}, 'clearing': {}},
            states={'ESZ24': state},
        )
        result = future_transact(view, "ESZ24", seller_id="market_maker", buyer_id="trader", qty=10, price=4500.0)

        # Two moves: seller->CH, CH->buyer
        assert len(result.moves) == 2
        # Check buyer gets the contracts
        buyer_move = next(m for m in result.moves if m.dest == "trader")
        assert buyer_move.source == "clearing"
        assert buyer_move.quantity == Decimal("10")

        # Check buyer's virtual_cash: -qty * price * mult = -10 * 4500 * 50 = -2,250,000
        sc = next(d for d in result.state_changes if d.unit == "ESZ24")
        w = sc.new_state['wallets']['trader']
        assert w['virtual_cash'] == -2_250_000.0

    def test_sell_to_market_maker(self):
        """Trader sells to market_maker: trader sells, market_maker buys"""
        # Trader has 10 contracts entered at 4500
        state = {**self.state, 'wallets': {'trader': {'position': Decimal("10"), 'virtual_cash': -2_250_000.0}}}
        view = FakeView(
            balances={'trader': {'ESZ24': Decimal("10")}, 'market_maker': {}, 'clearing': {}},
            states={'ESZ24': state},
        )
        result = future_transact(view, "ESZ24", seller_id="trader", buyer_id="market_maker", qty=5, price=4520.0)

        # Two moves: seller->CH, CH->buyer
        assert len(result.moves) == 2

        # Check seller's virtual_cash: old + qty * price * mult = -2,250,000 + 5 * 4520 * 50 = -1,120,000
        sc = next(d for d in result.state_changes if d.unit == "ESZ24")
        w = sc.new_state['wallets']['trader']
        assert w['virtual_cash'] == -1_120_000.0

    def test_virtual_cash_accumulates(self):
        """Adding to position accumulates virtual_cash"""
        # Alice has 10 contracts, market_maker sells 10 more
        state = {**self.state, 'wallets': {
            'alice': {'position': Decimal("10"), 'virtual_cash': -2_250_000.0},
            'market_maker': {'position': Decimal("100"), 'virtual_cash': Decimal("0.0")}
        }}
        view = FakeView(
            balances={'alice': {'ESZ24': Decimal("10")}, 'market_maker': {'ESZ24': Decimal("100")}, 'clearing': {}},
            states={'ESZ24': state},
        )
        # Buy 10 more at 4600
        result = future_transact(view, "ESZ24", seller_id="market_maker", buyer_id="alice", qty=10, price=4600.0)
        sc = next(d for d in result.state_changes if d.unit == "ESZ24")
        w = sc.new_state['wallets']['alice']

        # virtual_cash = -2,250,000 + (-10 * 4600 * 50) = -2,250,000 - 2,300,000 = -4,550,000
        assert w['virtual_cash'] == -4_550_000.0

    def test_settled_contract_raises(self):
        state = {**self.state, 'settled': True}
        view = FakeView(balances={}, states={'ESZ24': state})
        with pytest.raises(ValueError, match="Cannot trade settled contract"):
            future_transact(view, "ESZ24", seller_id="market_maker", buyer_id="trader", qty=10, price=4500.0)

    def test_zero_qty_raises(self):
        view = FakeView(balances={}, states={'ESZ24': self.state})
        with pytest.raises(ValueError, match="qty must be positive"):
            future_transact(view, "ESZ24", seller_id="market_maker", buyer_id="trader", qty=0, price=4500.0)


# ============================================================================
# FUTURE_CONTRACT - AUTOMATIC MTM AND EXPIRY
# ============================================================================

class TestFutureContract:
    """Tests for the SmartContract that handles daily MTM and expiry."""

    def test_daily_mtm_profit(self):
        """Price up = long profits"""
        # Alice has 10 contracts entered at 4500
        # virtual_cash = -10 * 4500 * 50 = -2,250,000
        state = {
            'underlying': 'SPX', 'expiry': datetime(2024, 12, 20), 'multiplier': Decimal("50.0"),
            'currency': 'USD', 'clearinghouse': 'clearing',
            'wallets': {'alice': {'position': Decimal("10"), 'virtual_cash': -2_250_000.0}},
            'settled': False,
        }
        view = FakeView(
            balances={'alice': {'ESZ24': Decimal("10")}, 'clearing': {'ESZ24': -10}},
            states={'ESZ24': state},
        )
        # Price goes to 4520
        # target_vcash = -10 * 4520 * 50 = -2,260,000
        # vm = -2,250,000 - (-2,260,000) = +10,000
        result = future_contract(view, "ESZ24", datetime(2024, 11, 1), {'SPX': Decimal("4520.0")})

        assert len(result.moves) == 1
        m = result.moves[0]
        assert m.source == "clearing"
        assert m.dest == "alice"
        assert m.quantity == Decimal("10000.0")

        # virtual_cash updated to target
        sc = next(d for d in result.state_changes if d.unit == "ESZ24")
        assert sc.new_state['wallets']['alice']['virtual_cash'] == -2_260_000.0

    def test_daily_mtm_loss(self):
        """Price down = long loses"""
        # Bob has 5 contracts entered at 4550
        # virtual_cash = -5 * 4550 * 50 = -1,137,500
        state = {
            'underlying': 'SPX', 'expiry': datetime(2024, 12, 20), 'multiplier': Decimal("50.0"),
            'currency': 'USD', 'clearinghouse': 'clearing',
            'wallets': {'bob': {'position': Decimal("5"), 'virtual_cash': -1_137_500.0}},
            'settled': False,
        }
        view = FakeView(
            balances={'bob': {'ESZ24': Decimal("5")}, 'clearing': {'ESZ24': -5}},
            states={'ESZ24': state},
        )
        # Price goes to 4520
        # target_vcash = -5 * 4520 * 50 = -1,130,000
        # vm = -1,137,500 - (-1,130,000) = -7,500
        result = future_contract(view, "ESZ24", datetime(2024, 11, 1), {'SPX': Decimal("4520.0")})

        m = result.moves[0]
        assert m.source == "bob"
        assert m.dest == "clearing"
        assert m.quantity == Decimal("7500.0")

    def test_multi_holder_settlement(self):
        """Alice profits, Bob loses - same settlement"""
        # Alice: 10 contracts at 4500, vcash = -2,250,000
        # Bob: 5 contracts at 4550, vcash = -1,137,500
        state = {
            'underlying': 'SPX', 'expiry': datetime(2024, 12, 20), 'multiplier': Decimal("50.0"),
            'currency': 'USD', 'clearinghouse': 'clearing',
            'wallets': {
                'alice': {'position': Decimal("10"), 'virtual_cash': -2_250_000.0},
                'bob': {'position': Decimal("5"), 'virtual_cash': -1_137_500.0},
            },
            'settled': False,
        }
        view = FakeView(
            balances={'alice': {'ESZ24': Decimal("10")}, 'bob': {'ESZ24': Decimal("5")}, 'clearing': {'ESZ24': -15}},
            states={'ESZ24': state},
        )
        # Price to 4520
        # Alice: target = -2,260,000, vm = -2,250,000 - (-2,260,000) = +10,000
        # Bob: target = -1,130,000, vm = -1,137,500 - (-1,130,000) = -7,500
        result = future_contract(view, "ESZ24", datetime(2024, 11, 1), {'SPX': Decimal("4520.0")})

        assert len(result.moves) == 2
        alice_move = next(m for m in result.moves if 'alice' in m.contract_id)
        bob_move = next(m for m in result.moves if 'bob' in m.contract_id)

        assert alice_move.source == "clearing"
        assert alice_move.quantity == Decimal("10000.0")

        assert bob_move.source == "bob"
        assert bob_move.quantity == Decimal("7500.0")

    def test_short_position_inverted_pnl(self):
        """Short position: price up = loss"""
        # Short has -5 contracts entered at 4500
        # virtual_cash = -(-5) * 4500 * 50 = +1,125,000
        state = {
            'underlying': 'SPX', 'expiry': datetime(2024, 12, 20), 'multiplier': Decimal("50.0"),
            'currency': 'USD', 'clearinghouse': 'clearing',
            'wallets': {'short': {'position': -5, 'virtual_cash': Decimal("1125000.0")}},
            'settled': False,
        }
        view = FakeView(
            balances={'short': {'ESZ24': -5}, 'clearing': {'ESZ24': Decimal("5")}},
            states={'ESZ24': state},
        )
        # Price up to 4520
        # target_vcash = -(-5) * 4520 * 50 = +1,130,000
        # vm = 1,125,000 - 1,130,000 = -5,000 (loss for short)
        result = future_contract(view, "ESZ24", datetime(2024, 11, 1), {'SPX': Decimal("4520.0")})

        m = result.moves[0]
        assert m.source == "short"
        assert m.dest == "clearing"
        assert m.quantity == Decimal("5000.0")

    def test_expiry_settles_and_marks_settled(self):
        """At expiry, final MTM + mark as settled"""
        expiry = datetime(2024, 12, 20)
        # Alice has 10 contracts at 4500
        # virtual_cash = -10 * 4500 * 50 = -2,250,000
        state = {
            'underlying': 'SPX', 'expiry': expiry, 'multiplier': Decimal("50.0"),
            'currency': 'USD', 'clearinghouse': 'clearing',
            'wallets': {'alice': {'position': Decimal("10"), 'virtual_cash': -2_250_000.0}},
            'settled': False,
        }
        view = FakeView(
            balances={'alice': {'ESZ24': Decimal("10")}, 'clearing': {'ESZ24': -10}},
            states={'ESZ24': state},
        )
        # Final price 4600
        # target = -10 * 4600 * 50 = -2,300,000
        # vm = -2,250,000 - (-2,300,000) = +50,000
        result = future_contract(view, "ESZ24", expiry, {'SPX': Decimal("4600.0")})

        assert result.moves[0].quantity == 50000.0
        sc = next(d for d in result.state_changes if d.unit == "ESZ24")
        assert sc.new_state['settled'] is True
        assert sc.new_state['settlement_price'] == 4600.0

    def test_before_expiry_not_settled(self):
        """MTM before expiry does not mark as settled"""
        state = {
            'underlying': 'SPX', 'expiry': datetime(2024, 12, 20), 'multiplier': Decimal("50.0"),
            'currency': 'USD', 'clearinghouse': 'clearing',
            'wallets': {'alice': {'position': Decimal("10"), 'virtual_cash': -2_250_000.0}},
            'settled': False,
        }
        view = FakeView(
            balances={'alice': {'ESZ24': Decimal("10")}, 'clearing': {'ESZ24': -10}},
            states={'ESZ24': state},
        )
        result = future_contract(view, "ESZ24", datetime(2024, 12, 19), {'SPX': Decimal("4520.0")})

        sc = next(d for d in result.state_changes if d.unit == "ESZ24")
        assert sc.new_state.get('settled') is False

    def test_no_price_raises(self):
        """No underlying price raises ValueError"""
        state = {
            'underlying': 'SPX', 'expiry': datetime(2024, 12, 20), 'multiplier': Decimal("50.0"),
            'currency': 'USD', 'clearinghouse': 'clearing',
            'wallets': {'alice': {'position': Decimal("10"), 'virtual_cash': -2_250_000.0}},
            'settled': False,
        }
        view = FakeView(
            balances={'alice': {'ESZ24': Decimal("10")}},
            states={'ESZ24': state},
        )
        with pytest.raises(ValueError, match="Missing price for future underlying 'SPX'"):
            future_contract(view, "ESZ24", datetime(2024, 11, 1), {})

    def test_already_settled_returns_empty(self):
        """Settled contract returns empty"""
        state = {
            'underlying': 'SPX', 'expiry': datetime(2024, 12, 20), 'multiplier': Decimal("50.0"),
            'currency': 'USD', 'clearinghouse': 'clearing', 'wallets': {}, 'settled': True,
        }
        view = FakeView(balances={}, states={'ESZ24': state})
        result = future_contract(view, "ESZ24", datetime(2024, 12, 20), {'SPX': Decimal("4600.0")})
        assert result.is_empty()

    def test_no_move_on_zero_change(self):
        """Price unchanged from entry = no move needed"""
        # Trader has 10 contracts at 4500
        # virtual_cash = -10 * 4500 * 50 = -2,250,000
        state = {
            'underlying': 'SPX', 'expiry': datetime(2024, 12, 20), 'multiplier': Decimal("50.0"),
            'currency': 'USD', 'clearinghouse': 'clearing',
            'wallets': {'trader': {'position': Decimal("10"), 'virtual_cash': -2_250_000.0}},
            'settled': False,
        }
        view = FakeView(
            balances={'trader': {'ESZ24': Decimal("10")}, 'clearing': {}},
            states={'ESZ24': state},
        )
        # Price stays at 4500
        # target = -10 * 4500 * 50 = -2,250,000
        # vm = -2,250,000 - (-2,250,000) = 0
        result = future_contract(view, "ESZ24", datetime(2024, 11, 1), {'SPX': Decimal("4500.0")})
        assert len(result.moves) == 0


# ============================================================================
# CLOSED POSITION SETTLEMENT
# ============================================================================

class TestClosedPosition:
    """Tests for settling wallets that closed their positions."""

    def test_closed_position_settles_vcash(self):
        """Wallet with zero position but non-zero vcash gets settled"""
        # Trader sold 10 at 4500, then bought 10 at 4520 (closed position)
        # vcash = +2,250,000 - 2,260,000 = -10,000 (realized loss)
        state = {
            'underlying': 'SPX', 'expiry': datetime(2024, 12, 20), 'multiplier': Decimal("50.0"),
            'currency': 'USD', 'clearinghouse': 'clearing',
            'wallets': {'trader': {'position': Decimal("0"), 'virtual_cash': -10_000.0}},
            'settled': False,
        }
        view = FakeView(
            balances={'trader': {'ESZ24': Decimal("0")}, 'clearing': {}},
            states={'ESZ24': state},
        )
        # MTM should settle the -10,000
        # target = -0 * price * mult = 0
        # vm = -10,000 - 0 = -10,000 (trader pays)
        result = future_contract(view, "ESZ24", datetime(2024, 11, 1), {'SPX': Decimal("4500.0")})

        assert len(result.moves) == 1
        m = result.moves[0]
        assert m.source == "trader"
        assert m.dest == "clearing"
        assert m.quantity == Decimal("10000.0")

        # Wallet should be removed after settlement
        sc = next(d for d in result.state_changes if d.unit == "ESZ24")
        assert 'trader' not in sc.new_state['wallets']


# ============================================================================
# MULTI-CURRENCY
# ============================================================================

class TestMultiCurrency:
    def test_eur_settlement(self):
        # Trader has 5 contracts at 500, vcash = -5 * 500 * 10 = -25,000
        state = {
            'underlying': 'SX5E', 'expiry': datetime(2024, 12, 20), 'multiplier': Decimal("10.0"),
            'currency': 'EUR', 'clearinghouse': 'eurex',
            'wallets': {'trader': {'position': Decimal("5"), 'virtual_cash': -25_000.0}},
            'settled': False,
        }
        view = FakeView(
            balances={'trader': {'FESX': Decimal("5")}, 'eurex': {}},
            states={'FESX': state},
        )
        # Price to 510
        # target = -5 * 510 * 10 = -25,500
        # vm = -25,000 - (-25, Decimal("500")) = +500 EUR
        result = future_contract(view, "FESX", datetime(2024, 11, 1), {'SX5E': Decimal("510.0")})
        assert result.moves[0].unit_symbol == 'EUR'
        assert result.moves[0].quantity == 500.0


# ============================================================================
# CONSERVATION
# ============================================================================

class TestConservation:
    def test_mtm_is_zero_sum(self):
        """Clearinghouse flow = negative of trader flow"""
        # Alice: 10 contracts at 4500, vcash = -2,250,000
        # Bob: 5 contracts at 4550, vcash = -1,137,500
        state = {
            'underlying': 'SPX', 'expiry': datetime(2024, 12, 20), 'multiplier': Decimal("50.0"),
            'currency': 'USD', 'clearinghouse': 'clearing',
            'wallets': {
                'alice': {'position': Decimal("10"), 'virtual_cash': -2_250_000.0},
                'bob': {'position': Decimal("5"), 'virtual_cash': -1_137_500.0},
            },
            'settled': False,
        }
        view = FakeView(
            balances={'alice': {'ESZ24': Decimal("10")}, 'bob': {'ESZ24': Decimal("5")}, 'clearing': {'ESZ24': -15}},
            states={'ESZ24': state},
        )
        # Price to 4520
        # Alice: vm = -2,250,000 - (-2,260,000) = +10,000
        # Bob: vm = -1,137,500 - (-1,130,000) = -7,500
        result = future_contract(view, "ESZ24", datetime(2024, 11, 1), {'SPX': Decimal("4520.0")})

        clearing_flow = 0
        for m in result.moves:
            if m.source == 'clearing':
                clearing_flow -= m.quantity
            elif m.dest == 'clearing':
                clearing_flow += m.quantity
        # Alice gets 10000, Bob pays 7500, net = -2500 for clearing
        assert clearing_flow == Decimal("-2500.0")
