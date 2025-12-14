"""
test_lifecycle_scenarios.py - End-to-end lifecycle scenario tests

Tests complete instrument lifecycles:
- Dividend payment cycles
- Option trade to settlement
- Forward trade to delivery
- Delta hedge full lifecycle
- Mixed instruments
- Multi-day complex scenarios
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from ledger import (
    Ledger, Move, build_transaction,
    cash,
    create_stock_unit,
    create_option_unit,
    create_forward_unit,
    create_delta_hedge_unit,
    LifecycleEngine,
    stock_contract,
    option_contract,
    forward_contract,
    delta_hedge_contract,
    deferred_cash_contract,
    compute_option_settlement,
    compute_forward_settlement,
    compute_liquidation,
    compute_hedge_pnl_breakdown,
    TimeSeriesPricingSource,
    Dividend,
)


class TestDividendLifecycle:
    """Tests for complete dividend payment lifecycle."""

    def test_quarterly_dividends(self):
        """Four quarterly dividends paid correctly."""
        schedule = [
            Dividend(datetime(2025, 3, 15), datetime(2025, 3, 15), 0.25, "USD"),
            Dividend(datetime(2025, 6, 15), datetime(2025, 6, 15), 0.25, "USD"),
            Dividend(datetime(2025, 9, 15), datetime(2025, 9, 15), 0.25, "USD"),
            Dividend(datetime(2025, 12, 15), datetime(2025, 12, 15), 0.25, "USD"),
        ]

        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_stock_unit(
            "AAPL", "Apple", "treasury", "USD",
            dividend_schedule=schedule, shortable=True
        ))

        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("treasury")

        ledger.set_balance("alice", "AAPL", Decimal("1000"))  # $250/quarter
        ledger.set_balance("bob", "AAPL", Decimal("500"))     # $125/quarter
        ledger.set_balance("treasury", "USD", Decimal("10000000"))

        alice_initial = ledger.get_balance("alice", "USD")
        bob_initial = ledger.get_balance("bob", "USD")

        engine = LifecycleEngine(ledger)
        engine.register("STOCK", stock_contract)
        engine.register("DEFERRED_CASH", deferred_cash_contract)

        # Process all quarterly payments
        for date in [datetime(2025, 3, 15), datetime(2025, 6, 15),
                     datetime(2025, 9, 15), datetime(2025, 12, 15)]:
            ledger.advance_time(date)
            engine.step(date, {"AAPL": Decimal("150.0")})

        # Verify total dividends received
        # alice: 1000 shares × $0.25 × 4 = $1000
        # bob: 500 shares × $0.25 × 4 = $500
        assert ledger.get_balance("alice", "USD") == alice_initial + Decimal("1000.0")
        assert ledger.get_balance("bob", "USD") == bob_initial + Decimal("500.0")

    def test_dividend_proportional_to_shares(self):
        """Dividend amount proportional to share holdings."""
        schedule = [Dividend(datetime(2025, 3, 15), datetime(2025, 3, 15), 1.0, "USD")]  # $1 dividend

        ledger = Ledger("test", datetime(2025, 3, 15), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_stock_unit(
            "AAPL", "Apple", "treasury", "USD",
            dividend_schedule=schedule
        ))

        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("charlie")
        ledger.register_wallet("treasury")

        # Different holdings
        ledger.set_balance("alice", "AAPL", Decimal("100"))
        ledger.set_balance("bob", "AAPL", Decimal("200"))
        ledger.set_balance("charlie", "AAPL", Decimal("300"))
        ledger.set_balance("treasury", "USD", Decimal("10000000"))

        engine = LifecycleEngine(ledger)
        engine.register("STOCK", stock_contract)
        engine.register("DEFERRED_CASH", deferred_cash_contract)
        engine.step(datetime(2025, 3, 15), {"AAPL": Decimal("150.0")})

        assert ledger.get_balance("alice", "USD") == Decimal("100.0")
        assert ledger.get_balance("bob", "USD") == Decimal("200.0")
        assert ledger.get_balance("charlie", "USD") == Decimal("300.0")


class TestOptionLifecycle:
    """Tests for complete option lifecycle."""

    def test_call_option_itm_lifecycle(self):
        """Call option: trade -> hold -> exercise ITM."""
        maturity = datetime(2025, 6, 20)

        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_stock_unit("AAPL", "Apple", "treasury", "USD", shortable=True))

        option = create_option_unit(
            "AAPL_C150", "AAPL Call $150", "AAPL", 150.0,
            maturity, "call", 100, "USD", "alice", "bob"
        )
        ledger.register_unit(option)

        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("treasury")

        # Initial positions
        ledger.set_balance("alice", "USD", Decimal("100000"))
        ledger.set_balance("bob", "AAPL", Decimal("1000"))
        ledger.set_balance("bob", "USD", Decimal("50000"))

        # Trade: alice buys 5 contracts from bob
        # Premium: let's say $500 per contract = $2500 total
        tx = build_transaction(ledger, [
            Move(Decimal("2500.0"), "USD", "alice", "bob", "premium"),
        ])
        ledger.execute(tx)

        # Set option positions
        ledger.set_balance("alice", "AAPL_C150", Decimal("5"))
        ledger.set_balance("bob", "AAPL_C150", -5)

        # Record balances before settlement
        alice_usd_before = ledger.get_balance("alice", "USD")
        bob_aapl_before = ledger.get_balance("bob", "AAPL")

        # Settle at maturity - ITM at $170
        ledger.advance_time(maturity)
        engine = LifecycleEngine(ledger)
        engine.register("BILATERAL_OPTION", option_contract)
        engine.step(maturity, {"AAPL": Decimal("170.0")})

        # Verify settlement
        state = ledger.get_unit_state("AAPL_C150")
        assert state["settled"] is True
        assert state["exercised"] is True

        # alice should have received 500 AAPL (5 contracts × 100 shares)
        # alice should have paid 5 × 100 × $150 = $75,000
        assert ledger.get_balance("alice", "AAPL") == Decimal("500")
        assert ledger.get_balance("alice", "USD") == alice_usd_before - 75000

    def test_call_option_otm_lifecycle(self):
        """Call option: trade -> hold -> expire worthless OTM."""
        maturity = datetime(2025, 6, 20)

        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_stock_unit("AAPL", "Apple", "treasury", "USD", shortable=True))

        option = create_option_unit(
            "AAPL_C150", "AAPL Call $150", "AAPL", 150.0,
            maturity, "call", 100, "USD", "alice", "bob"
        )
        ledger.register_unit(option)

        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("treasury")

        ledger.set_balance("alice", "AAPL_C150", Decimal("5"))
        ledger.set_balance("bob", "AAPL_C150", -5)
        ledger.set_balance("alice", "USD", Decimal("100000"))
        ledger.set_balance("bob", "AAPL", Decimal("1000"))

        alice_usd_before = ledger.get_balance("alice", "USD")

        # Settle at maturity - OTM at $140
        ledger.advance_time(maturity)
        engine = LifecycleEngine(ledger)
        engine.register("BILATERAL_OPTION", option_contract)
        engine.step(maturity, {"AAPL": Decimal("140.0")})

        # Verify expired worthless
        state = ledger.get_unit_state("AAPL_C150")
        assert state["settled"] is True
        assert state["exercised"] is False

        # alice's USD should be unchanged (no exercise)
        assert ledger.get_balance("alice", "USD") == alice_usd_before

    def test_put_option_itm_lifecycle(self):
        """Put option: exercise ITM."""
        maturity = datetime(2025, 6, 20)

        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_stock_unit("AAPL", "Apple", "treasury", "USD", shortable=True))

        option = create_option_unit(
            "AAPL_P150", "AAPL Put $150", "AAPL", 150.0,
            maturity, "put", 100, "USD", "alice", "bob"
        )
        ledger.register_unit(option)

        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("treasury")

        ledger.set_balance("alice", "AAPL_P150", Decimal("5"))
        ledger.set_balance("bob", "AAPL_P150", -5)
        ledger.set_balance("alice", "AAPL", Decimal("1000"))  # alice has shares to deliver
        ledger.set_balance("bob", "USD", Decimal("100000"))   # bob has cash to pay

        alice_aapl_before = ledger.get_balance("alice", "AAPL")

        # Settle ITM at $130
        ledger.advance_time(maturity)
        engine = LifecycleEngine(ledger)
        engine.register("BILATERAL_OPTION", option_contract)
        engine.step(maturity, {"AAPL": Decimal("130.0")})

        # alice delivers shares, receives cash
        # 5 contracts × 100 shares = 500 shares delivered
        # Receives 5 × 100 × $150 = $75,000
        assert ledger.get_balance("alice", "AAPL") == alice_aapl_before - 500
        assert ledger.get_balance("alice", "USD") == Decimal("75000")


class TestForwardLifecycle:
    """Tests for complete forward contract lifecycle."""

    def test_forward_delivery(self):
        """Forward: trade -> hold -> delivery."""
        delivery = datetime(2025, 6, 20)

        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_stock_unit("AAPL", "Apple", "treasury", "USD", shortable=True))

        forward = create_forward_unit(
            "AAPL_FWD", "AAPL Forward", "AAPL", 160.0,
            delivery, 100, "USD", "alice", "bob"
        )
        ledger.register_unit(forward)

        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("treasury")

        ledger.set_balance("alice", "AAPL_FWD", Decimal("5"))
        ledger.set_balance("bob", "AAPL_FWD", -5)
        ledger.set_balance("alice", "USD", Decimal("100000"))
        ledger.set_balance("bob", "AAPL", Decimal("1000"))

        alice_usd_before = ledger.get_balance("alice", "USD")

        # Deliver at delivery date
        ledger.advance_time(delivery)
        engine = LifecycleEngine(ledger)
        engine.register("BILATERAL_FORWARD", forward_contract)
        engine.step(delivery, {"AAPL": Decimal("170.0")})

        # alice pays 5 × 100 × $160 = $80,000
        # alice receives 500 shares
        assert ledger.get_balance("alice", "USD") == alice_usd_before - 80000
        assert ledger.get_balance("alice", "AAPL") == Decimal("500")

        # Verify settled
        state = ledger.get_unit_state("AAPL_FWD")
        assert state["settled"] is True


class TestDeltaHedgeLifecycle:
    """Tests for complete delta hedge lifecycle."""

    def test_delta_hedge_full_lifecycle(self):
        """Delta hedge: initialize -> rebalance -> liquidate."""
        maturity = datetime(2025, 6, 20)
        start = datetime(2025, 1, 1)

        ledger = Ledger("test", start, verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_stock_unit("AAPL", "Apple", "treasury", "USD", shortable=True))

        hedge = create_delta_hedge_unit(
            "HEDGE", "Test Hedge", "AAPL", 150.0,
            maturity, 0.25, 10, 100, "USD", "trader", "market", 0.0
        )
        ledger.register_unit(hedge)

        ledger.register_wallet("trader")
        ledger.register_wallet("market")
        ledger.register_wallet("treasury")

        initial_trader_usd = 500000.0
        ledger.set_balance("trader", "USD", initial_trader_usd)
        ledger.set_balance("market", "USD", Decimal("10000000"))
        ledger.set_balance("market", "AAPL", Decimal("100000"))

        # Generate price path to maturity
        days = (maturity - start).days
        prices = [(start + timedelta(days=i), 150 + i * 0.2) for i in range(days + 1)]
        pricing = TimeSeriesPricingSource({"AAPL": prices}, "USD")

        engine = LifecycleEngine(ledger)
        engine.register("DELTA_HEDGE_STRATEGY", delta_hedge_contract(min_trade_size=0.01))

        # Run until maturity
        for date, price in prices[:-1]:  # All but last
            ledger.advance_time(date)
            engine.step(date, {"AAPL": price})

        # Check rebalancing occurred
        state = ledger.get_unit_state("HEDGE")
        assert state["rebalance_count"] > 0
        assert state["current_shares"] > 0
        assert state["liquidated"] is False

        # Liquidate at maturity
        final_date, final_price = prices[-1]
        ledger.advance_time(final_date)

        result = compute_liquidation(ledger, "HEDGE", final_price)
        ledger.execute(result)

        # Verify liquidated
        state = ledger.get_unit_state("HEDGE")
        assert state["liquidated"] is True
        assert state["current_shares"] == 0

        # Compute P&L
        pnl = compute_hedge_pnl_breakdown(ledger, "HEDGE", final_price)
        assert "net_pnl" in pnl
        assert "option_payoff" in pnl


class TestMixedInstrumentsLifecycle:
    """Tests with multiple instrument types."""

    def test_mixed_portfolio_lifecycle(self):
        """Portfolio with stocks, options, and forwards."""
        option_maturity = datetime(2025, 6, 20)
        forward_delivery = datetime(2025, 9, 20)

        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))

        # Stock with dividends
        schedule = [Dividend(datetime(2025, 3, 15), datetime(2025, 3, 15), 0.25, "USD")]
        ledger.register_unit(create_stock_unit(
            "AAPL", "Apple", "treasury", "USD",
            dividend_schedule=schedule, shortable=True
        ))

        # Option
        option = create_option_unit(
            "AAPL_C150", "AAPL Call", "AAPL", 150.0,
            option_maturity, "call", 100, "USD", "alice", "bob"
        )
        ledger.register_unit(option)

        # Forward
        forward = create_forward_unit(
            "AAPL_FWD", "AAPL Forward", "AAPL", 160.0,
            forward_delivery, 100, "USD", "alice", "bob"
        )
        ledger.register_unit(forward)

        # Register wallets
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("treasury")

        # Setup positions
        ledger.set_balance("alice", "AAPL", Decimal("1000"))
        ledger.set_balance("alice", "AAPL_C150", Decimal("5"))
        ledger.set_balance("alice", "AAPL_FWD", Decimal("3"))
        ledger.set_balance("alice", "USD", Decimal("500000"))

        ledger.set_balance("bob", "AAPL", Decimal("2000"))
        ledger.set_balance("bob", "AAPL_C150", -5)
        ledger.set_balance("bob", "AAPL_FWD", -3)
        ledger.set_balance("bob", "USD", Decimal("500000"))

        ledger.set_balance("treasury", "USD", Decimal("10000000"))

        # Setup engine
        engine = LifecycleEngine(ledger)
        engine.register("STOCK", stock_contract)
        engine.register("DEFERRED_CASH", deferred_cash_contract)
        engine.register("BILATERAL_OPTION", option_contract)
        engine.register("BILATERAL_FORWARD", forward_contract)

        # Process dividend
        ledger.advance_time(datetime(2025, 3, 15))
        engine.step(datetime(2025, 3, 15), {"AAPL": Decimal("150.0")})

        # Verify dividend paid
        # alice: 1000 × $0.25 = $250
        # bob: 2000 × $0.25 = $500
        assert ledger.get_balance("alice", "USD") > 500000

        # Process option maturity
        ledger.advance_time(option_maturity)
        engine.step(option_maturity, {"AAPL": Decimal("170.0")})

        # Verify option settled
        assert ledger.get_unit_state("AAPL_C150")["settled"] is True

        # Process forward delivery
        ledger.advance_time(forward_delivery)
        engine.step(forward_delivery, {"AAPL": Decimal("180.0")})

        # Verify forward settled
        assert ledger.get_unit_state("AAPL_FWD")["settled"] is True


class TestCloneAtWithLifecycle:
    """Tests for clone_at with lifecycle events."""

    def test_clone_at_before_settlement(self):
        """clone_at before settlement shows unsettled state."""
        maturity = datetime(2025, 6, 20)

        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_stock_unit("AAPL", "Apple", "treasury", "USD", shortable=True))

        option = create_option_unit(
            "OPT", "Test Option", "AAPL", 150.0,
            maturity, "call", 100, "USD", "alice", "bob"
        )
        ledger.register_unit(option)

        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("treasury")

        ledger.set_balance("alice", "OPT", Decimal("5"))
        ledger.set_balance("bob", "OPT", -5)
        ledger.set_balance("alice", "USD", Decimal("100000"))
        ledger.set_balance("bob", "AAPL", Decimal("1000"))

        # Checkpoint before settlement
        checkpoint_time = datetime(2025, 6, 1)
        ledger.advance_time(checkpoint_time)

        # Settle
        ledger.advance_time(maturity)
        engine = LifecycleEngine(ledger)
        engine.register("BILATERAL_OPTION", option_contract)
        engine.step(maturity, {"AAPL": Decimal("170.0")})

        # Verify current state is settled
        assert ledger.get_unit_state("OPT")["settled"] is True

        # Clone at checkpoint - should be unsettled
        past = ledger.clone_at(checkpoint_time)
        assert past.get_unit_state("OPT")["settled"] is False
        assert past.get_balance("alice", "OPT") == Decimal("5")

    def test_clone_at_divergent_scenarios(self):
        """clone_at enables divergent scenario analysis."""
        maturity = datetime(2025, 6, 20)

        ledger = Ledger("test", datetime(2025, 1, 1), verbose=False, test_mode=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_unit(create_stock_unit("AAPL", "Apple", "treasury", "USD", shortable=True))

        option = create_option_unit(
            "OPT", "Test Option", "AAPL", 150.0,
            maturity, "call", 100, "USD", "alice", "bob"
        )
        ledger.register_unit(option)

        ledger.register_wallet("alice")
        ledger.register_wallet("bob")
        ledger.register_wallet("treasury")

        ledger.set_balance("alice", "OPT", Decimal("5"))
        ledger.set_balance("bob", "OPT", -5)
        ledger.set_balance("alice", "USD", Decimal("100000"))
        ledger.set_balance("bob", "AAPL", Decimal("1000"))

        # Checkpoint at start
        start = datetime(2025, 1, 1)

        # Settle in original timeline
        ledger.advance_time(maturity)
        engine = LifecycleEngine(ledger)
        engine.register("BILATERAL_OPTION", option_contract)
        engine.step(maturity, {"AAPL": Decimal("170.0")})

        # Create divergent timeline from start
        divergent = ledger.clone_at(start)

        # In divergent timeline, price tanks - option expires worthless
        divergent.advance_time(maturity)
        divergent_engine = LifecycleEngine(divergent)
        divergent_engine.register("BILATERAL_OPTION", option_contract)
        divergent_engine.step(maturity, {"AAPL": Decimal("130.0")})

        # Original: exercised
        assert ledger.get_unit_state("OPT")["exercised"] is True

        # Divergent: not exercised
        assert divergent.get_unit_state("OPT")["exercised"] is False
