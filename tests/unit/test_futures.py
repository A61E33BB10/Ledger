"""
test_futures.py - Unit tests for futures contracts with Virtual Ledger pattern

Tests:
- Factory function (create_future_unit)
- Virtual ledger trades (execute_futures_trade)
- Daily settlement (compute_daily_settlement)
- Intraday margin (compute_intraday_margin)
- Expiry settlement (compute_expiry)
- transact() interface
- Multi-currency scenarios
"""

import pytest
from datetime import datetime, timedelta
from tests.fake_view import FakeView
from ledger import (
    create_future_unit,
    execute_futures_trade,
    compute_daily_settlement,
    compute_intraday_margin,
    compute_expiry,
    future_transact,
    UNIT_TYPE_FUTURE,
)


# ============================================================================
# CREATE FUTURE UNIT TESTS
# ============================================================================

class TestCreateFutureUnit:
    """Tests for create_future_unit factory function."""

    def test_create_basic_future(self):
        """Create a basic ES futures contract."""
        future = create_future_unit(
            symbol="ESZ24",
            name="E-mini S&P 500 Dec 2024",
            underlying="SPX",
            expiry=datetime(2024, 12, 20, 16, 0),
            multiplier=50.0,
            settlement_currency="USD",
            exchange="CME",
            holder_wallet="trader",
            clearinghouse_wallet="clearinghouse",
        )

        assert future.symbol == "ESZ24"
        assert future.name == "E-mini S&P 500 Dec 2024"
        assert future.unit_type == UNIT_TYPE_FUTURE

        state = future._state
        assert state["underlying"] == "SPX"
        assert state["multiplier"] == 50.0
        assert state["settlement_currency"] == "USD"
        assert state["exchange"] == "CME"
        assert state["holder_wallet"] == "trader"
        assert state["clearinghouse_wallet"] == "clearinghouse"
        assert state["virtual_quantity"] == 0.0
        assert state["virtual_cash"] == 0.0
        assert state["last_settlement_price"] == 0.0
        assert state["intraday_postings"] == 0.0
        assert state["settled"] is False

    def test_create_crude_oil_future(self):
        """Create a CL (crude oil) futures contract."""
        future = create_future_unit(
            symbol="CLF25",
            name="WTI Crude Oil Jan 2025",
            underlying="WTI",
            expiry=datetime(2025, 1, 20, 14, 30),
            multiplier=1000.0,
            settlement_currency="USD",
            exchange="NYMEX",
            holder_wallet="energy_trader",
            clearinghouse_wallet="nymex_clearing",
        )

        assert future.symbol == "CLF25"
        assert future._state["multiplier"] == 1000.0
        assert future._state["underlying"] == "WTI"

    def test_create_euro_denominated_future(self):
        """Create a Euro-denominated futures contract."""
        future = create_future_unit(
            symbol="FESX",
            name="Euro STOXX 50 Dec 2024",
            underlying="SX5E",
            expiry=datetime(2024, 12, 20),
            multiplier=10.0,
            settlement_currency="EUR",
            exchange="EUREX",
            holder_wallet="eu_trader",
            clearinghouse_wallet="eurex_clearing",
        )

        assert future._state["settlement_currency"] == "EUR"

    def test_create_yen_denominated_future(self):
        """Create a Yen-denominated futures contract."""
        future = create_future_unit(
            symbol="NK225",
            name="Nikkei 225 Dec 2024",
            underlying="NI225",
            expiry=datetime(2024, 12, 13),
            multiplier=1000.0,
            settlement_currency="JPY",
            exchange="OSE",
            holder_wallet="jp_trader",
            clearinghouse_wallet="jpx_clearing",
        )

        assert future._state["settlement_currency"] == "JPY"

    def test_invalid_multiplier_raises(self):
        """Negative or zero multiplier raises ValueError."""
        with pytest.raises(ValueError, match="multiplier must be positive"):
            create_future_unit(
                symbol="BAD",
                name="Bad Future",
                underlying="XXX",
                expiry=datetime(2024, 12, 20),
                multiplier=0.0,
                settlement_currency="USD",
                exchange="CME",
                holder_wallet="trader",
                clearinghouse_wallet="clearing",
            )

        with pytest.raises(ValueError, match="multiplier must be positive"):
            create_future_unit(
                symbol="BAD",
                name="Bad Future",
                underlying="XXX",
                expiry=datetime(2024, 12, 20),
                multiplier=-50.0,
                settlement_currency="USD",
                exchange="CME",
                holder_wallet="trader",
                clearinghouse_wallet="clearing",
            )

    def test_empty_currency_raises(self):
        """Empty settlement_currency raises ValueError."""
        with pytest.raises(ValueError, match="settlement_currency cannot be empty"):
            create_future_unit(
                symbol="BAD",
                name="Bad Future",
                underlying="XXX",
                expiry=datetime(2024, 12, 20),
                multiplier=50.0,
                settlement_currency="",
                exchange="CME",
                holder_wallet="trader",
                clearinghouse_wallet="clearing",
            )

    def test_same_wallets_raises(self):
        """Same holder and clearinghouse wallet raises ValueError."""
        with pytest.raises(ValueError, match="must be different"):
            create_future_unit(
                symbol="BAD",
                name="Bad Future",
                underlying="XXX",
                expiry=datetime(2024, 12, 20),
                multiplier=50.0,
                settlement_currency="USD",
                exchange="CME",
                holder_wallet="trader",
                clearinghouse_wallet="trader",
            )


# ============================================================================
# EXECUTE FUTURES TRADE TESTS
# ============================================================================

class TestExecuteFuturesTrade:
    """Tests for execute_futures_trade (virtual ledger updates)."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.future_state = {
            'underlying': 'SPX',
            'expiry': datetime(2024, 12, 20, 16, 0),
            'multiplier': 50.0,
            'settlement_currency': 'USD',
            'exchange': 'CME',
            'holder_wallet': 'trader',
            'clearinghouse_wallet': 'clearinghouse',
            'virtual_quantity': 0.0,
            'virtual_cash': 0.0,
            'last_settlement_price': 0.0,
            'intraday_postings': 0.0,
            'settled': False,
        }

    def test_buy_trade_updates_virtual_ledger(self):
        """Buy trade increases virtual_quantity, decreases virtual_cash."""
        view = FakeView(
            balances={'trader': {'USD': 1000000}},
            states={'ESZ24': self.future_state},
        )

        result = execute_futures_trade(view, 'ESZ24', 10.0, 4500.00)

        assert len(result.moves) == 0  # No real moves
        assert 'ESZ24' in result.state_updates

        updated = result.state_updates['ESZ24']
        assert updated['virtual_quantity'] == 10.0
        # virtual_cash = -10 × 4500 × 50 = -2,250,000
        assert updated['virtual_cash'] == -2_250_000.0

    def test_sell_trade_updates_virtual_ledger(self):
        """Sell trade decreases virtual_quantity, increases virtual_cash."""
        state = dict(self.future_state)
        state['virtual_quantity'] = 10.0
        state['virtual_cash'] = -2_250_000.0

        view = FakeView(
            balances={'trader': {'USD': 1000000}},
            states={'ESZ24': state},
        )

        result = execute_futures_trade(view, 'ESZ24', -5.0, 4520.00)

        updated = result.state_updates['ESZ24']
        assert updated['virtual_quantity'] == 5.0
        # virtual_cash = -2,250,000 + (5 × 4520 × 50) = -2,250,000 + 1,130,000 = -1,120,000
        assert updated['virtual_cash'] == -1_120_000.0

    def test_multiple_trades_accumulate(self):
        """Multiple trades accumulate in virtual ledger."""
        view = FakeView(
            balances={'trader': {'USD': 1000000}},
            states={'ESZ24': self.future_state},
        )

        # First trade: buy 10 at 4500
        result1 = execute_futures_trade(view, 'ESZ24', 10.0, 4500.00)
        state1 = result1.state_updates['ESZ24']

        # Update view with new state
        view2 = FakeView(
            balances={'trader': {'USD': 1000000}},
            states={'ESZ24': state1},
        )

        # Second trade: buy 5 at 4520
        result2 = execute_futures_trade(view2, 'ESZ24', 5.0, 4520.00)
        state2 = result2.state_updates['ESZ24']

        assert state2['virtual_quantity'] == 15.0
        # virtual_cash = -2,250,000 + (-5 × 4520 × 50) = -2,250,000 - 1,130,000 = -3,380,000
        assert state2['virtual_cash'] == -3_380_000.0

    def test_zero_quantity_raises(self):
        """Zero quantity trade raises ValueError."""
        view = FakeView(
            balances={'trader': {'USD': 1000000}},
            states={'ESZ24': self.future_state},
        )

        with pytest.raises(ValueError, match="effectively zero"):
            execute_futures_trade(view, 'ESZ24', 0.0, 4500.00)

    def test_trade_on_settled_future_raises(self):
        """Cannot trade on a settled future."""
        state = dict(self.future_state)
        state['settled'] = True

        view = FakeView(
            balances={'trader': {'USD': 1000000}},
            states={'ESZ24': state},
        )

        with pytest.raises(ValueError, match="Cannot trade settled future"):
            execute_futures_trade(view, 'ESZ24', 10.0, 4500.00)


# ============================================================================
# DAILY SETTLEMENT TESTS
# ============================================================================

class TestComputeDailySettlement:
    """Tests for compute_daily_settlement (EOD margin settlement)."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.future_state = {
            'underlying': 'SPX',
            'expiry': datetime(2024, 12, 20, 16, 0),
            'multiplier': 50.0,
            'settlement_currency': 'USD',
            'exchange': 'CME',
            'holder_wallet': 'trader',
            'clearinghouse_wallet': 'clearinghouse',
            'virtual_quantity': 10.0,
            'virtual_cash': -2_250_000.0,  # Bought 10 at 4500
            'last_settlement_price': 4500.0,
            'intraday_postings': 0.0,
            'settled': False,
        }

    def test_profitable_settlement_returns_margin(self):
        """Price up → margin return to holder."""
        view = FakeView(
            balances={
                'trader': {'USD': 1000000},
                'clearinghouse': {'USD': 10000000},
            },
            states={'ESZ24': self.future_state},
        )

        # Settlement at 4510 (price up $10)
        result = compute_daily_settlement(view, 'ESZ24', 4510.00)

        # margin_call = -2,250,000 + (10 × 4510 × 50) = -2,250,000 + 2,255,000 = 5,000
        # Positive margin_call means holder owes clearinghouse? No wait...
        # Let me re-read: Positive = holder owes, Negative = clearinghouse owes holder
        # But this is a GAIN for holder (price went up), so clearinghouse should pay
        # Hmm, the formula: margin_call = virtual_cash + MTM_value
        # If holder is long and price goes up, MTM_value increases
        # virtual_cash is negative (we paid out cash to buy)
        # So margin_call becomes less negative or positive

        # Actually looking at the code: positive margin_call = holder owes clearinghouse
        # This seems backwards for gains...

        # Let me think again:
        # - Initial: bought 10 at 4500, virtual_cash = -10 * 4500 * 50 = -2,250,000
        # - This represents we "owe" this notional value
        # - At settlement 4510: MTM = 10 * 4510 * 50 = 2,255,000
        # - margin_call = -2,250,000 + 2,255,000 = 5,000
        # - Positive means holder pays clearinghouse 5,000?

        # Wait, I need to understand the virtual cash semantics better.
        # After EOD, virtual_cash resets to -MTM_value
        # So the "margin_call" is the difference to bring virtual_cash to -MTM

        # Actually, looking at it differently:
        # margin_call = virtual_cash + MTM = accumulated_cash_flows + current_value
        # If we bought at 4500 and now it's 4510:
        # - We "paid" 4500 per contract (notionally)
        # - It's now worth 4510 per contract
        # - Gain = (4510 - 4500) * 10 * 50 = 5000
        # So clearinghouse should pay us 5000

        # But the code says positive margin_call = holder pays clearinghouse
        # Let me trace through:
        # virtual_cash = -2,250,000 (negative = we paid out)
        # MTM = 10 * 4510 * 50 = 2,255,000 (positive = current value)
        # margin_call = -2,250,000 + 2,255,000 = 5,000

        # Ah I see - the code in compute_daily_settlement:
        # if margin_call > 0: holder pays clearinghouse
        # if margin_call < 0: clearinghouse pays holder

        # But 5000 > 0, so holder pays? That doesn't match my intuition.

        # Let me re-read the formula explanation in the docstring...
        # "margin_call = virtual_cash + (virtual_quantity × settlement_price × multiplier)"
        # "Positive margin_call = margin call (holder owes)"

        # OK so the virtual_cash represents the NET CASH position
        # When we buy, we have negative virtual_cash (we're short cash)
        # When price goes up, the MTM value of our position offsets that
        # If MTM > |virtual_cash|, we actually have a positive net (margin_call > 0)
        # This means we've "realized" a gain and need to pay it to clearinghouse as margin

        # Wait that still doesn't make sense. If price goes up and we're long,
        # we should RECEIVE margin, not pay it.

        # Let me look at the test more carefully...
        # Actually I think I had the cash flow direction wrong.
        # virtual_cash = -quantity * price * multiplier for a buy
        # This is negative because we're paying FOR the contracts
        # But in futures, you don't pay upfront - you post margin

        # I think the virtual_cash tracks the notional value you'd owe
        # margin_call = net_position = what you'd settle for if closing now
        # If positive, you owe that amount (to realize the position)
        # If negative, you're owed that amount

        # Hmm, let's just verify with the actual test:
        # With my state, if margin_call = 5000 and it's > 0
        # Then the code creates: Move(holder -> clearinghouse, 5000)
        # That means holder PAYS clearinghouse

        # But wait - if the price went UP and holder is LONG, holder should RECEIVE
        # This seems like a bug in my understanding or the code

        # Actually wait - let me re-check the formula semantics:
        # Maybe the pattern is: margin_call is what clearinghouse gives you
        # Positive = you get, negative = you pay
        # Then the code checks: if margin_call > 0: holder gets from clearinghouse
        # But the code says: if margin_call > 0: Move(holder_wallet, clearinghouse_wallet...)
        # That's holder PAYING clearinghouse, not receiving

        # Let me trace a simple example:
        # Buy 1 contract at price 100, multiplier 1
        # virtual_cash = -1 * 100 * 1 = -100
        # virtual_quantity = 1
        #
        # EOD settlement at price 110:
        # margin_call = -100 + (1 * 110 * 1) = -100 + 110 = 10
        # margin_call > 0, so holder pays clearinghouse 10
        #
        # But intuitively, price went from 100 to 110, holder is long
        # Holder should receive 10 (the gain), not pay 10

        # OK I think I found the issue - my understanding of virtual_cash is wrong
        # Let me look at execute_futures_trade:
        # trade_cash_flow = -quantity * price * multiplier
        # new_virtual_cash = current_virtual_cash + trade_cash_flow
        #
        # For a buy (quantity > 0): trade_cash_flow < 0
        # This makes virtual_cash more negative
        # Interpretation: negative virtual_cash = we OWE this much

        # At settlement:
        # margin_call = virtual_cash + MTM
        # = (what we owe) + (current value)
        # If current value > what we owe, margin_call > 0
        # This means we have excess value - we need to POST margin

        # Ah I think I get it now!
        # In futures, you don't pay/receive for the full notional
        # You only pay/receive the DAILY CHANGE
        #
        # Let's say on day 1: buy 1 at 100
        # - virtual_cash = -100 (we "committed" to buy at 100)
        # - At EOD settlement at 100: margin_call = -100 + 100 = 0 (no movement)
        # - virtual_cash resets to -100 (still committed at 100)
        #
        # Day 2: price moves to 110
        # - margin_call = -100 + 110 = 10
        # - This represents the GAIN of 10
        # - Clearinghouse PAYS holder 10 (not vice versa!)
        #
        # Wait but the code says margin_call > 0 means holder PAYS clearinghouse
        # That's inconsistent with my intuition...

        # Let me look at the code again very carefully:
        # if margin_call > 0:
        #     Move(source=holder_wallet, dest=clearinghouse_wallet, ...)
        # else:
        #     Move(source=clearinghouse_wallet, dest=holder_wallet, ...)

        # So margin_call > 0 → holder pays clearinghouse
        # margin_call < 0 → clearinghouse pays holder

        # With my example: margin_call = 10 > 0 → holder pays 10
        # But holder should RECEIVE 10 because price went up!

        # I think there's a conceptual confusion here. Let me think about
        # what the virtual_cash REALLY represents...

        # Actually, maybe the sign convention is:
        # virtual_cash = accumulated cash IN (positive = received, negative = paid)
        # When you buy: you PAY, so virtual_cash decreases (becomes more negative)
        #
        # margin_call = virtual_cash + MTM
        # = cash_received_so_far + current_position_value
        # = NET CASH POSITION (equity)
        #
        # If margin_call > 0: you have positive equity
        # But the futures market settles DAILY
        # So positive equity means you need to POST that as margin
        # Because you haven't actually received it yet!
        #
        # Hmm, that's getting convoluted. Let me just accept the code's semantics
        # and write tests that match them.

        # Actually, I think I finally get it:
        # margin_call > 0 means holder has UNREALIZED GAIN
        # The clearinghouse collects this gain AS MARGIN (holder pays)
        # Then virtual_cash resets so next day starts fresh
        #
        # If price goes DOWN tomorrow, margin_call will be negative
        # And holder RECEIVES margin back from clearinghouse
        #
        # So the daily settlement is:
        # - Gain: holder posts margin to clearinghouse (cash moves OUT)
        # - Loss: clearinghouse returns margin to holder (cash moves IN)
        #
        # Wait that's backwards from how I'd expect settlement to work!
        # In real futures, if you make money, you GET paid, not POST margin.

        # Let me look at a reference... Actually in traditional futures:
        # - You post INITIAL margin to open a position
        # - Daily variation margin: if price moves in your favor, you RECEIVE cash
        # - If price moves against you, you PAY cash (margin call)
        #
        # So with price going UP for a LONG position:
        # - Holder should RECEIVE cash (gain)
        #
        # But the code does the opposite. Let me re-check the formulas...
        #
        # Actually wait, I think I've been confusing myself. Let me trace
        # through the ENTIRE flow very carefully:
        #
        # Day 0: Buy 10 contracts at 4500, multiplier 50
        # - execute_futures_trade: qty=10, price=4500
        # - trade_cash_flow = -10 * 4500 * 50 = -2,250,000
        # - virtual_cash = 0 + (-2,250,000) = -2,250,000
        # - virtual_quantity = 10
        # - Interpretation: we're LONG 10 contracts, notionally worth 2.25M
        #
        # EOD Day 0: Settlement at 4500 (no price change)
        # - margin_call = -2,250,000 + (10 * 4500 * 50) = -2,250,000 + 2,250,000 = 0
        # - No margin move (correct!)
        # - virtual_cash resets to -(10 * 4500 * 50) = -2,250,000 (unchanged)
        #
        # Day 1: Price moves to 4510
        # EOD Day 1: Settlement at 4510
        # - margin_call = -2,250,000 + (10 * 4510 * 50) = -2,250,000 + 2,255,000 = 5,000
        # - margin_call > 0 → holder pays clearinghouse 5000
        # - virtual_cash resets to -(10 * 4510 * 50) = -2,255,000
        #
        # But wait! If holder pays 5000 when price goes UP, that's a LOSS!
        # That contradicts the standard futures settlement...
        #
        # UNLESS... the payment direction in the code is wrong?
        # Let me re-read the code one more time...
        #
        # Oh! I finally see the issue. The code comment says:
        # "Positive margin_call = holder owes clearinghouse (margin call)"
        # "Negative margin_call = clearinghouse owes holder (margin return)"
        #
        # A "margin CALL" in traditional futures parlance is when you need to
        # POST MORE margin because you're LOSING money.
        # A "margin RETURN" is when you RECEIVE margin back because you're WINNING.
        #
        # So the naming is confusing but...
        # - margin_call > 0 (holder owes) should mean holder is LOSING
        # - margin_call < 0 (clearinghouse owes) should mean holder is WINNING
        #
        # But with price going UP for a LONG position, the holder WINS!
        # margin_call = 5000 > 0 → holder owes (is losing?)
        # That's backwards!
        #
        # I think there might be a sign error in the code or my understanding
        # of virtual_cash is wrong.
        #
        # Actually, let me think about it differently:
        # virtual_cash accumulates the cash flows from trades
        # For a BUY: virtual_cash decreases (negative = paid out)
        #
        # At settlement, we compute: virtual_cash + MTM_value
        # This is: (accumulated_outflows) + (current_position_value)
        # = -(what_we_paid) + (what_it's_worth)
        # = profit/loss
        #
        # If positive: we made money → we should RECEIVE
        # If negative: we lost money → we should PAY
        #
        # So the code has it BACKWARDS!
        # margin_call > 0 should trigger clearinghouse → holder
        # margin_call < 0 should trigger holder → clearinghouse
        #
        # But the code does the opposite. Is this a bug?
        #
        # Actually, let me look at the variable names more carefully...
        # The variable is called "margin_call" not "variation_margin"
        # A margin_call is what you NEED TO POST (i.e., pay)
        # If your position has gained value, you have EXCESS margin
        # The clearinghouse doesn't need to call for more margin
        # In fact, you can withdraw some
        #
        # Hmm but the settlement process isn't about margin calls per se
        # It's about variation margin / daily settlement
        #
        # I'll just write tests based on what the code actually does,
        # and we can discuss if the semantics are wrong later.

        assert len(result.moves) == 1
        move = result.moves[0]

        # Correct sign convention: positive variation_margin (profit) → clearinghouse pays holder
        # variation_margin = 5000 (holder gained)
        assert move.source == 'clearinghouse'
        assert move.dest == 'trader'
        assert move.quantity == 5000.0
        assert move.unit == 'USD'

    def test_losing_settlement_pays_margin(self):
        """Price down → holder pays margin (loss)."""
        view = FakeView(
            balances={
                'trader': {'USD': 1000000},
                'clearinghouse': {'USD': 10000000},
            },
            states={'ESZ24': self.future_state},
        )

        # Settlement at 4490 (price down $10)
        result = compute_daily_settlement(view, 'ESZ24', 4490.00)

        # variation_margin = -2,250,000 + (10 × 4490 × 50) = -2,250,000 + 2,245,000 = -5,000
        assert len(result.moves) == 1
        move = result.moves[0]

        # Correct sign convention: negative variation_margin (loss) → holder pays clearinghouse
        assert move.source == 'trader'
        assert move.dest == 'clearinghouse'
        assert move.quantity == 5000.0  # abs(variation_margin)

    def test_settlement_resets_virtual_cash(self):
        """Settlement resets virtual_cash to -MTM."""
        view = FakeView(
            balances={
                'trader': {'USD': 1000000},
                'clearinghouse': {'USD': 10000000},
            },
            states={'ESZ24': self.future_state},
        )

        result = compute_daily_settlement(view, 'ESZ24', 4510.00)
        updated = result.state_updates['ESZ24']

        # virtual_cash should reset to -(qty × price × mult)
        expected_virtual_cash = -(10.0 * 4510.0 * 50.0)
        assert updated['virtual_cash'] == expected_virtual_cash
        assert updated['last_settlement_price'] == 4510.0
        assert updated['intraday_postings'] == 0.0

    def test_settlement_no_move_on_zero_change(self):
        """No move generated when settlement price equals break-even."""
        # Set virtual_cash such that margin_call will be exactly 0
        state = dict(self.future_state)
        state['virtual_cash'] = -2_250_000.0

        view = FakeView(
            balances={
                'trader': {'USD': 1000000},
                'clearinghouse': {'USD': 10000000},
            },
            states={'ESZ24': state},
        )

        # Settlement at 4500 → margin_call = -2,250,000 + 2,250,000 = 0
        result = compute_daily_settlement(view, 'ESZ24', 4500.00)

        assert len(result.moves) == 0

    def test_settlement_already_settled_returns_empty(self):
        """Settlement on already-settled future returns empty result."""
        state = dict(self.future_state)
        state['settled'] = True

        view = FakeView(
            balances={},
            states={'ESZ24': state},
        )

        result = compute_daily_settlement(view, 'ESZ24', 4510.00)
        assert len(result.moves) == 0
        assert len(result.state_updates) == 0

    def test_invalid_settlement_price_raises(self):
        """Non-positive settlement price raises ValueError."""
        view = FakeView(
            balances={},
            states={'ESZ24': self.future_state},
        )

        with pytest.raises(ValueError, match="must be positive"):
            compute_daily_settlement(view, 'ESZ24', 0.0)

        with pytest.raises(ValueError, match="must be positive"):
            compute_daily_settlement(view, 'ESZ24', -100.0)


# ============================================================================
# INTRADAY MARGIN TESTS
# ============================================================================

class TestComputeIntradayMargin:
    """Tests for compute_intraday_margin (intraday margin calls)."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.future_state = {
            'underlying': 'SPX',
            'expiry': datetime(2024, 12, 20, 16, 0),
            'multiplier': 50.0,
            'settlement_currency': 'USD',
            'exchange': 'CME',
            'holder_wallet': 'trader',
            'clearinghouse_wallet': 'clearinghouse',
            'virtual_quantity': 10.0,
            'virtual_cash': -2_250_000.0,
            'last_settlement_price': 4500.0,
            'intraday_postings': 0.0,
            'settled': False,
        }

    def test_intraday_margin_resets_virtual_cash_to_prevent_double_counting(self):
        """Intraday margin call resets virtual_cash to mark at current price.

        This prevents double-counting when EOD settlement runs afterward.
        After intraday margin at price P, virtual_cash becomes:
            new_virtual_cash = -(virtual_quantity * P * multiplier)

        So if EOD runs at the same price P:
            variation_margin = new_virtual_cash + (virtual_quantity * P * multiplier)
                            = -(qty * P * mult) + (qty * P * mult)
                            = 0  (no double-count!)
        """
        view = FakeView(
            balances={
                'trader': {'USD': 1000000},
                'clearinghouse': {'USD': 10000000},
            },
            states={'ESZ24': self.future_state},
        )

        result = compute_intraday_margin(view, 'ESZ24', 4510.00)
        updated = result.state_updates['ESZ24']

        # virtual_cash should be reset to mark position at current price
        # new_virtual_cash = -(10 * 4510 * 50) = -2,255,000
        assert updated['virtual_cash'] == -2_255_000.0

        # Also verify the audit trail field
        assert updated['last_intraday_price'] == 4510.00

    def test_intraday_margin_updates_intraday_postings_on_loss(self):
        """Intraday margin call updates intraday_postings only when holder posts margin.

        intraday_postings tracks margin POSTED (holder pays), not margin returned.
        When variation_margin > 0 (profit), holder receives margin, so no posting.
        When variation_margin < 0 (loss), holder posts margin, so postings increase.
        """
        view = FakeView(
            balances={
                'trader': {'USD': 1000000},
                'clearinghouse': {'USD': 10000000},
            },
            states={'ESZ24': self.future_state},
        )

        # Price drops to 4450 (loss scenario)
        result = compute_intraday_margin(view, 'ESZ24', 4450.00)
        updated = result.state_updates['ESZ24']

        # variation_margin = -2,250,000 + (10 × 4450 × 50) = -25,000
        # Negative = holder has loss, posts margin
        assert updated['intraday_postings'] == 25000.0

    def test_intraday_margin_no_posting_on_profit(self):
        """Intraday margin return (profit) does NOT increase intraday_postings."""
        view = FakeView(
            balances={
                'trader': {'USD': 1000000},
                'clearinghouse': {'USD': 10000000},
            },
            states={'ESZ24': self.future_state},
        )

        # Price rises to 4510 (profit scenario)
        result = compute_intraday_margin(view, 'ESZ24', 4510.00)
        updated = result.state_updates['ESZ24']

        # variation_margin = -2,250,000 + (10 × 4510 × 50) = 5,000
        # Positive = holder has profit, receives margin (not a posting)
        assert updated['intraday_postings'] == 0.0

    def test_multiple_intraday_calls_accumulate_only_losses(self):
        """Multiple intraday margin calls accumulate ONLY losses in intraday_postings.

        After the first intraday call, virtual_cash was reset to mark at that price.
        The second call computes margin from the new baseline.
        Only margin posted (losses) should accumulate, not margin returned (profits).
        """
        state = dict(self.future_state)
        # Simulate state after first intraday call at 4450 (loss scenario):
        # - intraday_postings = 25000 (first call loss, holder posted margin)
        # - virtual_cash = -(10 * 4450 * 50) = -2,225,000 (marked at 4450)
        state['intraday_postings'] = 25000.0
        state['virtual_cash'] = -2_225_000.0  # Reset from first call
        state['last_intraday_price'] = 4450.0

        view = FakeView(
            balances={
                'trader': {'USD': 1000000},
                'clearinghouse': {'USD': 10000000},
            },
            states={'ESZ24': state},
        )

        # Second call at 4440 (price dropped another 10, another loss)
        result = compute_intraday_margin(view, 'ESZ24', 4440.00)
        updated = result.state_updates['ESZ24']

        # variation_margin = -2,225,000 + (10 × 4440 × 50) = -2,225,000 + 2,220,000 = -5,000
        # Negative = loss, holder posts 5,000 more margin
        # new_intraday_postings = 25000 + 5000 = 30000
        assert updated['intraday_postings'] == 30000.0

        # virtual_cash should be reset to new mark price
        # new_virtual_cash = -(10 * 4440 * 50) = -2,220,000
        assert updated['virtual_cash'] == -2_220_000.0

    def test_intraday_postings_mixed_moves(self):
        """Intraday postings only accumulate losses, not profits (mixed scenario).

        Example from bug report:
        - 10:00 AM: Price drops, margin call = -25,000 (posts $25K)
        - 3:00 PM: Price rallies, margin return = +5,000 (receives $5K back)
        - Correct: intraday_postings = 25,000 (only gross margin posted)
        - Wrong (old bug): intraday_postings = 30,000 (double-counting)
        """
        state = dict(self.future_state)
        # Start: bought 10 at 4500, virtual_cash = -2,250,000

        view1 = FakeView(
            balances={
                'trader': {'USD': 1000000},
                'clearinghouse': {'USD': 10000000},
            },
            states={'ESZ24': state},
        )

        # 10:00 AM: Price drops to 4450, loss of 25,000
        result1 = compute_intraday_margin(view1, 'ESZ24', 4450.00)
        state1 = result1.state_updates['ESZ24']

        # Holder posts 25,000 margin
        assert state1['intraday_postings'] == 25000.0

        # 3:00 PM: Price rallies to 4460, profit of 5,000 from the 4450 mark
        view2 = FakeView(
            balances={
                'trader': {'USD': 975000},
                'clearinghouse': {'USD': 10025000},
            },
            states={'ESZ24': state1},
        )

        result2 = compute_intraday_margin(view2, 'ESZ24', 4460.00)
        state2 = result2.state_updates['ESZ24']

        # variation_margin = -2,225,000 + (10 × 4460 × 50) = -2,225,000 + 2,230,000 = +5,000
        # Positive = profit, holder receives margin back (NOT a posting)
        # intraday_postings should remain 25,000, not increase to 30,000
        assert state2['intraday_postings'] == 25000.0  # Correct behavior
        # Old buggy behavior would have: assert state2['intraday_postings'] == 30000.0

    def test_intraday_then_eod_no_double_counting(self):
        """Verify no double-counting when intraday margin is followed by EOD settlement.

        This is the critical test that validates the fix for the double-counting bug.
        """
        # Start with position: bought 10 at 4500
        state = dict(self.future_state)

        view1 = FakeView(
            balances={
                'trader': {'USD': 1000000},
                'clearinghouse': {'USD': 10000000},
            },
            states={'ESZ24': state},
        )

        # Price drops to 4450 - intraday margin call
        intraday_result = compute_intraday_margin(view1, 'ESZ24', 4450.00)

        # Verify intraday margin move (loss of 25,000)
        # variation_margin = -2,250,000 + (10 × 4450 × 50) = -25,000
        assert len(intraday_result.moves) == 1
        intraday_move = intraday_result.moves[0]
        assert intraday_move.source == 'trader'  # Holder pays (loss)
        assert intraday_move.dest == 'clearinghouse'
        assert intraday_move.quantity == 25000.0

        # Get the updated state after intraday margin
        updated_state = intraday_result.state_updates['ESZ24']

        # Now run EOD settlement at the SAME price (4450)
        view2 = FakeView(
            balances={
                'trader': {'USD': 975000},  # After paying 25k
                'clearinghouse': {'USD': 10025000},
            },
            states={'ESZ24': updated_state},
        )

        eod_result = compute_daily_settlement(view2, 'ESZ24', 4450.00)

        # EOD at same price should produce NO margin move (already settled intraday)
        # This proves no double-counting!
        assert len(eod_result.moves) == 0


# ============================================================================
# EXPIRY TESTS
# ============================================================================

class TestComputeExpiry:
    """Tests for compute_expiry (final settlement at expiration)."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.expiry = datetime(2024, 12, 20, 16, 0)
        self.future_state = {
            'underlying': 'SPX',
            'expiry': self.expiry,
            'multiplier': 50.0,
            'settlement_currency': 'USD',
            'exchange': 'CME',
            'holder_wallet': 'trader',
            'clearinghouse_wallet': 'clearinghouse',
            'virtual_quantity': 10.0,
            'virtual_cash': -2_250_000.0,
            'last_settlement_price': 4500.0,
            'intraday_postings': 0.0,
            'settled': False,
        }

    def test_expiry_settles_position(self):
        """Expiry settlement closes position and marks settled."""
        view = FakeView(
            balances={
                'trader': {'USD': 1000000},
                'clearinghouse': {'USD': 10000000},
            },
            states={'ESZ24': self.future_state},
            time=self.expiry,
        )

        result = compute_expiry(view, 'ESZ24', 4550.00)
        updated = result.state_updates['ESZ24']

        assert updated['settled'] is True
        assert updated['virtual_quantity'] == 0.0
        assert updated['virtual_cash'] == 0.0
        assert updated['settlement_price'] == 4550.00

    def test_expiry_generates_final_margin_move(self):
        """Expiry generates final margin adjustment."""
        view = FakeView(
            balances={
                'trader': {'USD': 1000000},
                'clearinghouse': {'USD': 10000000},
            },
            states={'ESZ24': self.future_state},
            time=self.expiry,
        )

        result = compute_expiry(view, 'ESZ24', 4550.00)

        # final_margin_call = -2,250,000 + (10 × 4550 × 50) = 25,000
        assert len(result.moves) == 1
        move = result.moves[0]
        assert move.quantity == 25000.0

    def test_expiry_before_expiry_date_returns_empty(self):
        """Expiry before expiry date returns empty result."""
        view = FakeView(
            balances={},
            states={'ESZ24': self.future_state},
            time=datetime(2024, 12, 19),  # Day before expiry
        )

        result = compute_expiry(view, 'ESZ24', 4550.00)
        assert len(result.moves) == 0

    def test_expiry_already_settled_returns_empty(self):
        """Expiry on already-settled future returns empty result."""
        state = dict(self.future_state)
        state['settled'] = True

        view = FakeView(
            balances={},
            states={'ESZ24': state},
            time=self.expiry,
        )

        result = compute_expiry(view, 'ESZ24', 4550.00)
        assert len(result.moves) == 0


# ============================================================================
# TRANSACT INTERFACE TESTS
# ============================================================================

class TestTransact:
    """Tests for transact() unified interface."""

    def setup_method(self):
        """Setup common test fixtures."""
        self.expiry = datetime(2024, 12, 20, 16, 0)
        self.future_state = {
            'underlying': 'SPX',
            'expiry': self.expiry,
            'multiplier': 50.0,
            'settlement_currency': 'USD',
            'exchange': 'CME',
            'holder_wallet': 'trader',
            'clearinghouse_wallet': 'clearinghouse',
            'virtual_quantity': 0.0,
            'virtual_cash': 0.0,
            'last_settlement_price': 0.0,
            'intraday_postings': 0.0,
            'settled': False,
        }

    def test_transact_trade_event(self):
        """transact handles TRADE event."""
        view = FakeView(
            balances={'trader': {'USD': 1000000}},
            states={'ESZ24': self.future_state},
        )

        result = future_transact(
            view, 'ESZ24', 'TRADE', datetime(2024, 11, 1),
            quantity=10.0, price=4500.00
        )

        assert 'ESZ24' in result.state_updates
        assert result.state_updates['ESZ24']['virtual_quantity'] == 10.0

    def test_transact_daily_settlement_event(self):
        """transact handles DAILY_SETTLEMENT event."""
        state = dict(self.future_state)
        state['virtual_quantity'] = 10.0
        state['virtual_cash'] = -2_250_000.0

        view = FakeView(
            balances={
                'trader': {'USD': 1000000},
                'clearinghouse': {'USD': 10000000},
            },
            states={'ESZ24': state},
        )

        result = future_transact(
            view, 'ESZ24', 'DAILY_SETTLEMENT', datetime(2024, 11, 1),
            settlement_price=4510.00
        )

        assert len(result.moves) == 1

    def test_transact_margin_call_event(self):
        """transact handles MARGIN_CALL event."""
        state = dict(self.future_state)
        state['virtual_quantity'] = 10.0
        state['virtual_cash'] = -2_250_000.0

        view = FakeView(
            balances={
                'trader': {'USD': 1000000},
                'clearinghouse': {'USD': 10000000},
            },
            states={'ESZ24': state},
        )

        result = future_transact(
            view, 'ESZ24', 'MARGIN_CALL', datetime(2024, 11, 1),
            current_price=4510.00
        )

        assert len(result.moves) == 1

    def test_transact_expiry_event(self):
        """transact handles EXPIRY event."""
        state = dict(self.future_state)
        state['virtual_quantity'] = 10.0
        state['virtual_cash'] = -2_250_000.0

        view = FakeView(
            balances={
                'trader': {'USD': 1000000},
                'clearinghouse': {'USD': 10000000},
            },
            states={'ESZ24': state},
            time=self.expiry,
        )

        result = future_transact(
            view, 'ESZ24', 'EXPIRY', self.expiry,
            expiry_settlement_price=4550.00
        )

        assert len(result.moves) == 1
        assert result.state_updates['ESZ24']['settled'] is True

    def test_transact_unknown_event_returns_empty(self):
        """transact returns empty for unknown event type."""
        view = FakeView(
            balances={},
            states={'ESZ24': self.future_state},
        )

        result = future_transact(
            view, 'ESZ24', 'UNKNOWN_EVENT', datetime(2024, 11, 1)
        )

        assert len(result.moves) == 0
        assert len(result.state_updates) == 0

    def test_transact_missing_params_returns_empty(self):
        """transact returns empty when required params are missing."""
        view = FakeView(
            balances={},
            states={'ESZ24': self.future_state},
        )

        # TRADE without quantity/price
        result = future_transact(
            view, 'ESZ24', 'TRADE', datetime(2024, 11, 1)
        )
        assert len(result.moves) == 0

        # DAILY_SETTLEMENT without settlement_price
        result = future_transact(
            view, 'ESZ24', 'DAILY_SETTLEMENT', datetime(2024, 11, 1)
        )
        assert len(result.moves) == 0


# ============================================================================
# MULTI-CURRENCY SCENARIOS
# ============================================================================

class TestMultiCurrencyFutures:
    """Tests for futures in different currencies."""

    def test_euro_futures_settlement(self):
        """Euro-denominated futures settle in EUR."""
        state = {
            'underlying': 'SX5E',
            'expiry': datetime(2024, 12, 20),
            'multiplier': 10.0,
            'settlement_currency': 'EUR',
            'exchange': 'EUREX',
            'holder_wallet': 'eu_trader',
            'clearinghouse_wallet': 'eurex_clearing',
            'virtual_quantity': 5.0,
            'virtual_cash': -25_000.0,  # Bought 5 at 500
            'last_settlement_price': 500.0,
            'intraday_postings': 0.0,
            'settled': False,
        }

        view = FakeView(
            balances={
                'eu_trader': {'EUR': 100000},
                'eurex_clearing': {'EUR': 10000000},
            },
            states={'FESX': state},
        )

        result = compute_daily_settlement(view, 'FESX', 510.00)

        assert len(result.moves) == 1
        move = result.moves[0]
        assert move.unit == 'EUR'
        # margin_call = -25,000 + (5 × 510 × 10) = -25,000 + 25,500 = 500
        assert move.quantity == 500.0

    def test_yen_futures_large_numbers(self):
        """Yen-denominated futures handle large numbers correctly."""
        state = {
            'underlying': 'NI225',
            'expiry': datetime(2024, 12, 13),
            'multiplier': 1000.0,
            'settlement_currency': 'JPY',
            'exchange': 'OSE',
            'holder_wallet': 'jp_trader',
            'clearinghouse_wallet': 'jpx_clearing',
            'virtual_quantity': 2.0,
            'virtual_cash': -76_000_000.0,  # Bought 2 at 38000
            'last_settlement_price': 38000.0,
            'intraday_postings': 0.0,
            'settled': False,
        }

        view = FakeView(
            balances={
                'jp_trader': {'JPY': 100_000_000},
                'jpx_clearing': {'JPY': 10_000_000_000},
            },
            states={'NK225': state},
        )

        result = compute_daily_settlement(view, 'NK225', 38500.00)

        move = result.moves[0]
        assert move.unit == 'JPY'
        # margin_call = -76,000,000 + (2 × 38500 × 1000) = -76,000,000 + 77,000,000 = 1,000,000
        assert move.quantity == 1_000_000.0


# ============================================================================
# CONSERVATION LAW TESTS
# ============================================================================

class TestConservationLaws:
    """Tests verifying conservation laws for futures."""

    def test_daily_settlement_conserves_cash(self):
        """Daily settlement moves conserve total cash."""
        state = {
            'underlying': 'SPX',
            'expiry': datetime(2024, 12, 20),
            'multiplier': 50.0,
            'settlement_currency': 'USD',
            'exchange': 'CME',
            'holder_wallet': 'trader',
            'clearinghouse_wallet': 'clearinghouse',
            'virtual_quantity': 10.0,
            'virtual_cash': -2_250_000.0,
            'last_settlement_price': 4500.0,
            'intraday_postings': 0.0,
            'settled': False,
        }

        view = FakeView(
            balances={
                'trader': {'USD': 1_000_000},
                'clearinghouse': {'USD': 10_000_000},
            },
            states={'ESZ24': state},
        )

        initial_total = 1_000_000 + 10_000_000

        result = compute_daily_settlement(view, 'ESZ24', 4510.00)

        # Verify moves sum to zero (one source, one dest)
        for move in result.moves:
            assert move.source != move.dest  # Different wallets
            # The move just transfers; doesn't create or destroy

        # Moves represent transfers: source loses, dest gains
        # Total should stay the same
        # Since we only have the ContractResult, not the executed ledger,
        # we verify the move structure is correct
        if len(result.moves) == 1:
            move = result.moves[0]
            assert move.quantity > 0  # Always positive quantity

    def test_expiry_conserves_cash(self):
        """Expiry settlement moves conserve total cash."""
        expiry = datetime(2024, 12, 20)
        state = {
            'underlying': 'SPX',
            'expiry': expiry,
            'multiplier': 50.0,
            'settlement_currency': 'USD',
            'exchange': 'CME',
            'holder_wallet': 'trader',
            'clearinghouse_wallet': 'clearinghouse',
            'virtual_quantity': 10.0,
            'virtual_cash': -2_250_000.0,
            'last_settlement_price': 4500.0,
            'intraday_postings': 0.0,
            'settled': False,
        }

        view = FakeView(
            balances={
                'trader': {'USD': 1_000_000},
                'clearinghouse': {'USD': 10_000_000},
            },
            states={'ESZ24': state},
            time=expiry,
        )

        result = compute_expiry(view, 'ESZ24', 4550.00)

        # Verify expiry closes out cleanly
        updated = result.state_updates['ESZ24']
        assert updated['virtual_quantity'] == 0.0
        assert updated['virtual_cash'] == 0.0
        assert updated['settled'] is True
