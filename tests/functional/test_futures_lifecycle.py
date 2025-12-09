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
from ledger import (
    Ledger, cash, create_future, future_transact, future_contract, LifecycleEngine,
)


class TestMultiDayLifecycle:
    """Multi-day trading with automatic daily MTM."""

    def test_buy_hold_daily_mtm(self):
        """Buy futures, automatic MTM over 3 days."""
        ledger = Ledger("test", datetime(2024, 11, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_future(
            "ESZ24", "E-mini Dec 24", "SPX", datetime(2024, 12, 20), 50.0, "USD", "clearing"
        ))
        ledger.register_wallet("trader")
        ledger.register_wallet("clearing")
        ledger.set_balance("trader", "USD", 500_000)
        ledger.set_balance("clearing", "USD", 10_000_000)
        ledger.set_balance("clearing", "ESZ24", 1000)

        # Buy 10 at 4500 (positive qty)
        # virtual_cash = -10 * 4500 * 50 = -2,250,000
        ledger.execute_contract(future_transact(ledger, "ESZ24", "trader", qty=10, price=4500.0))
        assert ledger.get_balance("trader", "ESZ24") == 10.0
        assert ledger.get_unit_state("ESZ24")["wallets"]["trader"]["virtual_cash"] == -2_250_000.0

        # Day 1 EOD: MTM at 4505 (up $5)
        # target = -10 * 4505 * 50 = -2,252,500
        # vm = -2,250,000 - (-2,252,500) = +2,500
        ledger.execute_contract(future_contract(ledger, "ESZ24", datetime(2024, 11, 1), {"SPX": 4505.0}))
        assert ledger.get_balance("trader", "USD") == 502_500.0

        # Day 2 EOD: MTM at 4520 (up $15 from day 1)
        # target = -10 * 4520 * 50 = -2,260,000
        # vm = -2,252,500 - (-2,260,000) = +7,500
        ledger.execute_contract(future_contract(ledger, "ESZ24", datetime(2024, 11, 2), {"SPX": 4520.0}))
        assert ledger.get_balance("trader", "USD") == 510_000.0

        # Day 3 EOD: MTM at 4510 (down $10 from day 2)
        # target = -10 * 4510 * 50 = -2,255,000
        # vm = -2,260,000 - (-2,255,000) = -5,000
        ledger.execute_contract(future_contract(ledger, "ESZ24", datetime(2024, 11, 3), {"SPX": 4510.0}))
        assert ledger.get_balance("trader", "USD") == 505_000.0

        # Net: (4510-4500) * 10 * 50 = +5000
        assert ledger.get_balance("trader", "USD") == 500_000 + 5000

    def test_buy_and_sell_same_day(self):
        """Buy then partially sell before EOD MTM."""
        ledger = Ledger("test", datetime(2024, 11, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_future(
            "ESZ24", "E-mini Dec 24", "SPX", datetime(2024, 12, 20), 50.0, "USD", "clearing"
        ))
        ledger.register_wallet("trader")
        ledger.register_wallet("clearing")
        ledger.set_balance("trader", "USD", 500_000)
        ledger.set_balance("clearing", "USD", 10_000_000)
        ledger.set_balance("clearing", "ESZ24", 1000)

        # Buy 10 at 4500
        # vcash = -10 * 4500 * 50 = -2,250,000
        ledger.execute_contract(future_transact(ledger, "ESZ24", "trader", qty=10, price=4500.0))
        assert ledger.get_balance("trader", "ESZ24") == 10.0

        # Sell 3 at 4510 (negative qty)
        # vcash = -2,250,000 + 3 * 4510 * 50 = -2,250,000 + 676,500 = -1,573,500
        ledger.execute_contract(future_transact(ledger, "ESZ24", "trader", qty=-3, price=4510.0))
        assert ledger.get_balance("trader", "ESZ24") == 7.0

        # EOD MTM at 4520 - only 7 contracts now
        # target = -7 * 4520 * 50 = -1,582,000
        # vm = -1,573,500 - (-1,582,000) = +8,500
        ledger.execute_contract(future_contract(ledger, "ESZ24", datetime(2024, 11, 1), {"SPX": 4520.0}))
        assert ledger.get_unit_state("ESZ24")["wallets"]["trader"]["virtual_cash"] == -1_582_000.0


class TestMultiHolder:
    """Multiple holders with different entry prices."""

    def test_alice_and_bob(self):
        """Alice profits, Bob loses at same settlement price."""
        ledger = Ledger("test", datetime(2024, 11, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_future(
            "ESZ24", "E-mini Dec 24", "SPX", datetime(2024, 12, 20), 50.0, "USD", "clearing"
        ))
        for w in ["alice", "bob", "clearing"]:
            ledger.register_wallet(w)
        ledger.set_balance("alice", "USD", 500_000)
        ledger.set_balance("bob", "USD", 500_000)
        ledger.set_balance("clearing", "USD", 10_000_000)
        ledger.set_balance("clearing", "ESZ24", 1000)

        # Alice buys 10 at 4500
        ledger.execute_contract(future_transact(ledger, "ESZ24", "alice", qty=10, price=4500.0))

        # Bob buys 5 at 4550
        ledger.execute_contract(future_transact(ledger, "ESZ24", "bob", qty=5, price=4550.0))

        # MTM at 4520
        ledger.execute_contract(future_contract(ledger, "ESZ24", datetime(2024, 11, 1), {"SPX": 4520.0}))

        # Alice: (4520-4500)*10*50 = +10,000
        assert ledger.get_balance("alice", "USD") == 510_000.0

        # Bob: (4520-4550)*5*50 = -7,500
        assert ledger.get_balance("bob", "USD") == 492_500.0

        # Conservation
        total = sum(ledger.get_balance(w, "USD") for w in ["alice", "bob", "clearing"])
        assert total == 500_000 + 500_000 + 10_000_000


class TestExpiry:
    """Expiry settlement via SmartContract."""

    def test_expiry_settles_and_marks_settled(self):
        """At expiry, final MTM + mark as settled."""
        expiry = datetime(2024, 12, 20)
        ledger = Ledger("test", expiry, verbose=False)
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
        ledger.set_balance("trader", "ESZ24", 10.0)
        ledger.set_balance("clearing", "ESZ24", -10.0)
        ledger.update_unit_state("ESZ24", {
            **ledger.get_unit_state("ESZ24"),
            'wallets': {'trader': {'position': 10, 'virtual_cash': -2_250_000.0}},
        })

        # Expiry settlement via future_contract at 4550
        # target = -10 * 4550 * 50 = -2,275,000
        # vm = -2,250,000 - (-2,275,000) = +25,000
        ledger.execute_contract(future_contract(ledger, "ESZ24", expiry, {"SPX": 4550.0}))

        state = ledger.get_unit_state("ESZ24")
        assert state["settled"] is True
        assert state["settlement_price"] == 4550.0

        # VM = (4550-4500)*10*50 = 25,000
        assert ledger.get_balance("trader", "USD") == 525_000.0


class TestLifecycleEngine:
    """LifecycleEngine integration."""

    def test_auto_expiry(self):
        """LifecycleEngine auto-expires at expiry date."""
        expiry = datetime(2024, 12, 20)
        ledger = Ledger("test", datetime(2024, 12, 15), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_future(
            "ESZ24", "E-mini Dec 24", "SPX", expiry, 50.0, "USD", "clearing"
        ))
        ledger.register_wallet("trader")
        ledger.register_wallet("clearing")
        ledger.set_balance("trader", "USD", 500_000)
        ledger.set_balance("clearing", "USD", 10_000_000)

        # Setup position with correct virtual_cash (entered at 4500)
        ledger.set_balance("trader", "ESZ24", 10.0)
        ledger.set_balance("clearing", "ESZ24", -10.0)
        ledger.update_unit_state("ESZ24", {
            **ledger.get_unit_state("ESZ24"),
            'wallets': {'trader': {'position': 10, 'virtual_cash': -2_250_000.0}},
        })

        engine = LifecycleEngine(ledger)
        engine.register("FUTURE", future_contract)

        # Step through days until after expiry
        for day in range(15, 22):
            date = datetime(2024, 12, day)
            ledger.advance_time(date)
            engine.step(date, {"SPX": 4550.0})

        assert ledger.get_unit_state("ESZ24")["settled"] is True


class TestMultiCurrency:
    """Futures in different currencies."""

    def test_eur_futures(self):
        """Euro-denominated futures settle in EUR."""
        ledger = Ledger("test", datetime(2024, 11, 1), verbose=False)
        ledger.register_unit(cash("EUR", "Euro"))
        ledger.register_unit(create_future(
            "FESX", "Euro STOXX 50", "SX5E", datetime(2024, 12, 20), 10.0, "EUR", "eurex"
        ))
        ledger.register_wallet("trader")
        ledger.register_wallet("eurex")
        ledger.set_balance("trader", "EUR", 100_000)
        ledger.set_balance("eurex", "EUR", 10_000_000)
        ledger.set_balance("eurex", "FESX", 1000)

        # Buy 5 at 5000
        ledger.execute_contract(future_transact(ledger, "FESX", "trader", qty=5, price=5000.0))

        # MTM at 5050
        ledger.execute_contract(future_contract(ledger, "FESX", datetime(2024, 11, 1), {"SX5E": 5050.0}))

        # VM = (5050-5000)*5*10 = 2,500 EUR
        assert ledger.get_balance("trader", "EUR") == 102_500.0

    def test_jpy_large_notional(self):
        """Yen futures handle large numbers."""
        ledger = Ledger("test", datetime(2024, 11, 1), verbose=False)
        ledger.register_unit(cash("JPY", "Japanese Yen"))
        ledger.register_unit(create_future(
            "NK225", "Nikkei 225", "NI225", datetime(2024, 12, 13), 1000.0, "JPY", "jpx"
        ))
        ledger.register_wallet("trader")
        ledger.register_wallet("jpx")
        ledger.set_balance("trader", "JPY", 100_000_000)
        ledger.set_balance("jpx", "JPY", 10_000_000_000)
        ledger.set_balance("jpx", "NK225", 1000)

        # Buy 2 at 38000
        ledger.execute_contract(future_transact(ledger, "NK225", "trader", qty=2, price=38000.0))

        # MTM at 38500
        ledger.execute_contract(future_contract(ledger, "NK225", datetime(2024, 11, 1), {"NI225": 38500.0}))

        # VM = (38500-38000)*2*1000 = 1,000,000 JPY
        assert ledger.get_balance("trader", "JPY") == 101_000_000


class TestConservation:
    """Total cash must be conserved."""

    def test_mtm_conserves_cash(self):
        """Daily MTM is zero-sum."""
        ledger = Ledger("test", datetime(2024, 11, 1), verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_future(
            "ESZ24", "E-mini Dec 24", "SPX", datetime(2024, 12, 20), 50.0, "USD", "clearing"
        ))
        ledger.register_wallet("trader")
        ledger.register_wallet("clearing")
        ledger.set_balance("trader", "USD", 500_000)
        ledger.set_balance("clearing", "USD", 10_000_000)
        ledger.set_balance("clearing", "ESZ24", 1000)

        initial = ledger.get_balance("trader", "USD") + ledger.get_balance("clearing", "USD")

        ledger.execute_contract(future_transact(ledger, "ESZ24", "trader", qty=10, price=4500.0))
        ledger.execute_contract(future_contract(ledger, "ESZ24", datetime(2024, 11, 1), {"SPX": 4510.0}))

        final = ledger.get_balance("trader", "USD") + ledger.get_balance("clearing", "USD")
        assert final == initial

    def test_expiry_conserves_cash(self):
        """Expiry settlement is zero-sum."""
        expiry = datetime(2024, 12, 20)
        ledger = Ledger("test", expiry, verbose=False)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_future(
            "ESZ24", "E-mini Dec 24", "SPX", expiry, 50.0, "USD", "clearing"
        ))
        ledger.register_wallet("trader")
        ledger.register_wallet("clearing")
        ledger.set_balance("trader", "USD", 500_000)
        ledger.set_balance("clearing", "USD", 10_000_000)
        ledger.set_balance("trader", "ESZ24", 10.0)
        ledger.set_balance("clearing", "ESZ24", -10.0)
        ledger.update_unit_state("ESZ24", {
            **ledger.get_unit_state("ESZ24"),
            'wallets': {'trader': {'position': 10, 'virtual_cash': -2_250_000.0}},
        })

        initial = ledger.get_balance("trader", "USD") + ledger.get_balance("clearing", "USD")
        ledger.execute_contract(future_contract(ledger, "ESZ24", expiry, {"SPX": 4550.0}))
        final = ledger.get_balance("trader", "USD") + ledger.get_balance("clearing", "USD")

        assert final == initial
