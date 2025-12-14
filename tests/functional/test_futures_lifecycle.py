"""
test_futures_lifecycle.py - End-to-end lifecycle tests for multi-holder futures

Tests complete futures lifecycle:
- Trading with algebraic quantity (positive=buy, negative=sell)
- Automatic MTM via future_contract() SmartContract
- Expiry settlement via LifecycleEngine
- Multi-holder with different entry prices
- Multi-currency

=== THE VIRTUAL CASH MODEL ===

Per-wallet state:
    virtual_cash: Sum of (-qty * price * mult) for all trades

On TRADE: virtual_cash -= qty * price * mult
On MTM: vm = virtual_cash - (-position * price * mult), then reset
"""

import pytest
from datetime import datetime
from decimal import Decimal
from ledger import (
    Ledger, cash, create_future, future_transact, future_contract, LifecycleEngine,
)


class TestMultiDayLifecycle:
    """Multi-day trading with automatic daily MTM."""

    def test_buy_hold_daily_mtm(self):
        """Buy futures, automatic MTM over 3 days."""
        ledger = Ledger("test", datetime(2024, 11, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_future(
            "ESZ24", "E-mini Dec 24", "SPX", datetime(2024, 12, 20), 50.0, "USD", "clearing"
        ))
        ledger.register_wallet("trader")
        ledger.register_wallet("clearing")
        ledger.register_wallet("market_maker")
        ledger.set_balance("trader", "USD", 500_000)
        ledger.set_balance("clearing", "USD", 10_000_000)
        ledger.set_balance("market_maker", "ESZ24", Decimal("1000"))
        # Market maker entered at 4500: vcash = -1000 * 4500 * 50 = -225,000,000
        ledger.update_unit_state("ESZ24", {
            **ledger.get_unit_state("ESZ24"),
            'wallets': {'market_maker': {'position': Decimal("1000"), 'virtual_cash': -225_000_000.0}},
        })

        # Buy 10 at 4500: market_maker sells to trader (via clearinghouse)
        # virtual_cash = -10 * 4500 * 50 = -2,250,000
        ledger.execute(future_transact(ledger, "ESZ24", seller_id="market_maker", buyer_id="trader", qty=10, price=4500.0))
        assert ledger.get_balance("trader", "ESZ24") == Decimal("10.0")
        assert ledger.get_unit_state("ESZ24")["wallets"]["trader"]["virtual_cash"] == -2_250_000.0

        # Day 1 EOD: MTM at 4505 (up $5)
        # target = -10 * 4505 * 50 = -2,252,500
        # vm = -2,250,000 - (-2,252,500) = +2,500
        ledger.execute(future_contract(ledger, "ESZ24", datetime(2024, 11, 1), {"SPX": Decimal("4505.0")}))
        assert ledger.get_balance("trader", "USD") == Decimal("502500.0")

        # Day 2 EOD: MTM at 4520 (up $15 from day 1)
        # target = -10 * 4520 * 50 = -2,260,000
        # vm = -2,252,500 - (-2,260,000) = +7,500
        ledger.execute(future_contract(ledger, "ESZ24", datetime(2024, 11, 2), {"SPX": Decimal("4520.0")}))
        assert ledger.get_balance("trader", "USD") == Decimal("510000.0")

        # Day 3 EOD: MTM at 4510 (down $10 from day 2)
        # target = -10 * 4510 * 50 = -2,255,000
        # vm = -2,260,000 - (-2,255,000) = -5,000
        ledger.execute(future_contract(ledger, "ESZ24", datetime(2024, 11, 3), {"SPX": Decimal("4510.0")}))
        assert ledger.get_balance("trader", "USD") == Decimal("505000.0")

        # Net: (4510-4500) * 10 * 50 = +5000
        assert ledger.get_balance("trader", "USD") == Decimal("500000") + 5000

    def test_buy_and_sell_same_day(self):
        """Buy then partially sell before EOD MTM."""
        ledger = Ledger("test", datetime(2024, 11, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_future(
            "ESZ24", "E-mini Dec 24", "SPX", datetime(2024, 12, 20), 50.0, "USD", "clearing"
        ))
        ledger.register_wallet("trader")
        ledger.register_wallet("clearing")
        ledger.register_wallet("market_maker")
        ledger.set_balance("trader", "USD", 500_000)
        ledger.set_balance("clearing", "USD", 10_000_000)
        ledger.set_balance("market_maker", "ESZ24", Decimal("1000"))
        # Market maker entered at 4500: vcash = -1000 * 4500 * 50 = -225,000,000
        ledger.update_unit_state("ESZ24", {
            **ledger.get_unit_state("ESZ24"),
            'wallets': {'market_maker': {'position': Decimal("1000"), 'virtual_cash': -225_000_000.0}},
        })

        # Buy 10 at 4500: market_maker sells to trader
        # vcash = -10 * 4500 * 50 = -2,250,000
        ledger.execute(future_transact(ledger, "ESZ24", seller_id="market_maker", buyer_id="trader", qty=10, price=4500.0))
        assert ledger.get_balance("trader", "ESZ24") == Decimal("10.0")

        # Sell 3 at 4510: trader sells to market_maker
        # vcash = -2,250,000 + 3 * 4510 * 50 = -2,250,000 + 676,500 = -1,573,500
        ledger.execute(future_transact(ledger, "ESZ24", seller_id="trader", buyer_id="market_maker", qty=3, price=4510.0))
        assert ledger.get_balance("trader", "ESZ24") == Decimal("7.0")

        # EOD MTM at 4520 - only 7 contracts now
        # target = -7 * 4520 * 50 = -1,582,000
        # vm = -1,573,500 - (-1,582,000) = +8,500
        ledger.execute(future_contract(ledger, "ESZ24", datetime(2024, 11, 1), {"SPX": Decimal("4520.0")}))
        assert ledger.get_unit_state("ESZ24")["wallets"]["trader"]["virtual_cash"] == -1_582_000.0


class TestMultiHolder:
    """Multiple holders with different entry prices."""

    def test_alice_and_bob(self):
        """Alice profits, Bob loses at same settlement price."""
        ledger = Ledger("test", datetime(2024, 11, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_future(
            "ESZ24", "E-mini Dec 24", "SPX", datetime(2024, 12, 20), 50.0, "USD", "clearing"
        ))
        for w in ["alice", "bob", "clearing", "market_maker"]:
            ledger.register_wallet(w)
        ledger.set_balance("alice", "USD", 500_000)
        ledger.set_balance("bob", "USD", 500_000)
        ledger.set_balance("clearing", "USD", 10_000_000)
        ledger.set_balance("market_maker", "ESZ24", Decimal("1000"))
        # Market maker entered at 4500: vcash = -1000 * 4500 * 50 = -225,000,000
        ledger.update_unit_state("ESZ24", {
            **ledger.get_unit_state("ESZ24"),
            'wallets': {'market_maker': {'position': Decimal("1000"), 'virtual_cash': -225_000_000.0}},
        })

        # Alice buys 10 at 4500: market_maker sells to alice
        ledger.execute(future_transact(ledger, "ESZ24", seller_id="market_maker", buyer_id="alice", qty=10, price=4500.0))

        # Bob buys 5 at 4550: market_maker sells to bob
        ledger.execute(future_transact(ledger, "ESZ24", seller_id="market_maker", buyer_id="bob", qty=5, price=4550.0))

        # MTM at 4520
        ledger.execute(future_contract(ledger, "ESZ24", datetime(2024, 11, 1), {"SPX": Decimal("4520.0")}))

        # Alice: (4520-4500)*10*50 = +10,000
        assert ledger.get_balance("alice", "USD") == Decimal("510000.0")

        # Bob: (4520-4550)*5*50 = -7,500
        assert ledger.get_balance("bob", "USD") == Decimal("492500.0")

        # Conservation (clearing settles with all parties)
        total = sum(ledger.get_balance(w, "USD") for w in ["alice", "bob", "clearing", "market_maker"])
        assert total == 500_000 + 500_000 + 10_000_000


class TestExpiry:
    """Expiry settlement via SmartContract."""

    def test_expiry_settles_and_marks_settled(self):
        """At expiry, final MTM + mark as settled."""
        expiry = datetime(2024, 12, 20)
        ledger = Ledger("test", expiry, verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_future(
            "ESZ24", "E-mini Dec 24", "SPX", expiry, 50.0, "USD", "clearing"
        ))
        ledger.register_wallet("trader")
        ledger.register_wallet("clearing")
        ledger.set_balance("trader", "USD", 500_000)
        ledger.set_balance("clearing", "USD", 10_000_000)

        # Setup position directly with correct virtual_cash
        # Simulating entry at 4500: vcash = -10 * 4500 * 50 = -2,250,000
        ledger.set_balance("trader", "ESZ24", Decimal("10.0"))
        ledger.set_balance("clearing", "ESZ24", -10.0)
        ledger.update_unit_state("ESZ24", {
            **ledger.get_unit_state("ESZ24"),
            'wallets': {'trader': {'position': Decimal("10"), 'virtual_cash': -2_250_000.0}},
        })

        # Expiry settlement via future_contract at 4550
        # target = -10 * 4550 * 50 = -2,275,000
        # vm = -2,250,000 - (-2,275,000) = +25,000
        ledger.execute(future_contract(ledger, "ESZ24", expiry, {"SPX": Decimal("4550.0")}))

        state = ledger.get_unit_state("ESZ24")
        assert state["settled"] is True
        assert state["settlement_price"] == 4550.0

        # VM = (4550-4500)*10*50 = 25,000
        assert ledger.get_balance("trader", "USD") == Decimal("525000.0")


class TestLifecycleEngine:
    """LifecycleEngine integration."""

    def test_auto_expiry(self):
        """LifecycleEngine auto-expires at expiry date."""
        expiry = datetime(2024, 12, 20)
        ledger = Ledger("test", datetime(2024, 12, 15), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_future(
            "ESZ24", "E-mini Dec 24", "SPX", expiry, 50.0, "USD", "clearing"
        ))
        ledger.register_wallet("trader")
        ledger.register_wallet("clearing")
        ledger.set_balance("trader", "USD", 500_000)
        ledger.set_balance("clearing", "USD", 10_000_000)

        # Setup position with correct virtual_cash (entered at 4500)
        ledger.set_balance("trader", "ESZ24", Decimal("10.0"))
        ledger.set_balance("clearing", "ESZ24", -10.0)
        ledger.update_unit_state("ESZ24", {
            **ledger.get_unit_state("ESZ24"),
            'wallets': {'trader': {'position': Decimal("10"), 'virtual_cash': -2_250_000.0}},
        })

        engine = LifecycleEngine(ledger)
        engine.register("FUTURE", future_contract)

        # Step through days until after expiry
        for day in range(15, 22):
            date = datetime(2024, 12, day)
            ledger.advance_time(date)
            engine.step(date, {"SPX": Decimal("4550.0")})

        assert ledger.get_unit_state("ESZ24")["settled"] is True


class TestMultiCurrency:
    """Futures in different currencies."""

    def test_eur_futures(self):
        """Euro-denominated futures settle in EUR."""
        ledger = Ledger("test", datetime(2024, 11, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("EUR", "Euro"))
        ledger.register_unit(create_future(
            "FESX", "Euro STOXX 50", "SX5E", datetime(2024, 12, 20), 10.0, "EUR", "eurex"
        ))
        ledger.register_wallet("trader")
        ledger.register_wallet("eurex")
        ledger.register_wallet("market_maker")
        ledger.set_balance("trader", "EUR", 100_000)
        ledger.set_balance("eurex", "EUR", 10_000_000)
        ledger.set_balance("market_maker", "FESX", Decimal("1000"))
        # Market maker entered at 5000: vcash = -1000 * 5000 * 10 = -50,000,000
        ledger.update_unit_state("FESX", {
            **ledger.get_unit_state("FESX"),
            'wallets': {'market_maker': {'position': Decimal("1000"), 'virtual_cash': -50_000_000.0}},
        })

        # Buy 5 at 5000: market_maker sells to trader
        ledger.execute(future_transact(ledger, "FESX", seller_id="market_maker", buyer_id="trader", qty=5, price=5000.0))

        # MTM at 5050
        ledger.execute(future_contract(ledger, "FESX", datetime(2024, 11, 1), {"SX5E": Decimal("5050.0")}))

        # VM = (5050-5000)*5*10 = 2,500 EUR
        assert ledger.get_balance("trader", "EUR") == Decimal("102500.0")

    def test_jpy_large_notional(self):
        """Yen futures handle large numbers."""
        ledger = Ledger("test", datetime(2024, 11, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("JPY", "Japanese Yen"))
        ledger.register_unit(create_future(
            "NK225", "Nikkei 225", "NI225", datetime(2024, 12, 13), 1000.0, "JPY", "jpx"
        ))
        ledger.register_wallet("trader")
        ledger.register_wallet("jpx")
        ledger.register_wallet("market_maker")
        ledger.set_balance("trader", "JPY", 100_000_000)
        ledger.set_balance("jpx", "JPY", 50_000_000_000)  # More cash for large settlements
        ledger.set_balance("market_maker", "NK225", Decimal("1000"))
        # Market maker's position entered at 38000, vcash = -1000 * 38000 * 1000 = -38,000,000,000
        ledger.update_unit_state("NK225", {
            **ledger.get_unit_state("NK225"),
            'wallets': {'market_maker': {'position': Decimal("1000"), 'virtual_cash': -38_000_000_000.0}},
        })

        # Buy 2 at 38000: market_maker sells to trader
        ledger.execute(future_transact(ledger, "NK225", seller_id="market_maker", buyer_id="trader", qty=2, price=38000.0))

        # MTM at 38500
        ledger.execute(future_contract(ledger, "NK225", datetime(2024, 11, 1), {"NI225": Decimal("38500.0")}))

        # VM = (38500-38000)*2*1000 = 1,000,000 JPY
        assert ledger.get_balance("trader", "JPY") == Decimal("101000000")


class TestConservation:
    """Total cash must be conserved."""

    def test_mtm_conserves_cash(self):
        """Daily MTM is zero-sum."""
        ledger = Ledger("test", datetime(2024, 11, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_future(
            "ESZ24", "E-mini Dec 24", "SPX", datetime(2024, 12, 20), 50.0, "USD", "clearing"
        ))
        ledger.register_wallet("trader")
        ledger.register_wallet("clearing")
        ledger.register_wallet("market_maker")
        ledger.set_balance("trader", "USD", 500_000)
        ledger.set_balance("clearing", "USD", 10_000_000)
        ledger.set_balance("market_maker", "ESZ24", Decimal("1000"))
        # Market maker entered at 4500: vcash = -1000 * 4500 * 50 = -225,000,000
        ledger.update_unit_state("ESZ24", {
            **ledger.get_unit_state("ESZ24"),
            'wallets': {'market_maker': {'position': Decimal("1000"), 'virtual_cash': -225_000_000.0}},
        })

        initial = sum(ledger.get_balance(w, "USD") for w in ["trader", "clearing", "market_maker"])

        ledger.execute(future_transact(ledger, "ESZ24", seller_id="market_maker", buyer_id="trader", qty=10, price=4500.0))
        ledger.execute(future_contract(ledger, "ESZ24", datetime(2024, 11, 1), {"SPX": Decimal("4510.0")}))

        final = sum(ledger.get_balance(w, "USD") for w in ["trader", "clearing", "market_maker"])
        assert final == initial

    def test_expiry_conserves_cash(self):
        """Expiry settlement is zero-sum."""
        expiry = datetime(2024, 12, 20)
        ledger = Ledger("test", expiry, verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_future(
            "ESZ24", "E-mini Dec 24", "SPX", expiry, 50.0, "USD", "clearing"
        ))
        ledger.register_wallet("trader")
        ledger.register_wallet("clearing")
        ledger.set_balance("trader", "USD", 500_000)
        ledger.set_balance("clearing", "USD", 10_000_000)
        ledger.set_balance("trader", "ESZ24", Decimal("10.0"))
        ledger.set_balance("clearing", "ESZ24", -10.0)
        ledger.update_unit_state("ESZ24", {
            **ledger.get_unit_state("ESZ24"),
            'wallets': {'trader': {'position': Decimal("10"), 'virtual_cash': -2_250_000.0}},
        })

        initial = ledger.get_balance("trader", "USD") + ledger.get_balance("clearing", "USD")
        ledger.execute(future_contract(ledger, "ESZ24", expiry, {"SPX": Decimal("4550.0")}))
        final = ledger.get_balance("trader", "USD") + ledger.get_balance("clearing", "USD")

        assert final == initial
