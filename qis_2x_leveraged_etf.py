#!/usr/bin/env python3
"""
2x Leveraged SPX ETF Demo

This demonstrates a QIS (Quantitative Investment Strategy) that replicates
a 2x leveraged ETF with daily rebalancing.

Key concepts:
- Self-financing: NAV before rebalance = NAV after rebalance
- Leverage via negative cash (borrowing)
- Daily rebalancing to maintain target leverage
- Financing costs on borrowed funds
- Path dependency: 2x daily returns != 2x period return

Usage:
    python examples/qis_2x_leveraged_etf.py
"""

from datetime import datetime, timedelta
from ledger import (
    Ledger, cash, Move, build_transaction, SYSTEM_WALLET,
    create_qis, leveraged_strategy, qis_contract,
    get_qis_nav, get_qis_return, get_qis_leverage,
)


def main():
    print("=" * 70)
    print("2x LEVERAGED SPX ETF SIMULATION")
    print("=" * 70)

    # Setup
    inception = datetime(2025, 1, 1)
    ledger = Ledger("2x_etf_demo", initial_time=inception)
    ledger.register_unit(cash("USD", "US Dollar"))
    ledger.register_wallet("dealer")
    ledger.register_wallet("investor")
    # SYSTEM_WALLET is auto-registered

    # Fund wallets
    fund = build_transaction(ledger, [
        Move(1_000_000.0, "USD", SYSTEM_WALLET, "dealer", "fund_dealer"),
        Move(100_000.0, "USD", SYSTEM_WALLET, "investor", "fund_investor"),
    ])
    ledger.execute(fund)

    print(f"\nInitial balances:")
    print(f"  Dealer:   ${ledger.get_balance('dealer', 'USD'):,.2f}")
    print(f"  Investor: ${ledger.get_balance('investor', 'USD'):,.2f}")

    # Create daily rebalance schedule for one week
    rebalance_dates = [inception + timedelta(days=i) for i in range(7)]
    maturity = inception + timedelta(days=7)

    # Create QIS
    qis = create_qis(
        symbol="QIS_2X_SPX",
        name="2x Leveraged SPX ETF",
        notional=100_000,  # $100K notional
        initial_nav=100.0,
        funding_rate=0.05,  # 5% annual borrowing cost
        payer_wallet="dealer",
        receiver_wallet="investor",
        currency="USD",
        eligible_assets=["SPX"],
        rebalance_dates=rebalance_dates,
        maturity_date=maturity,
        inception_date=inception,
    )
    ledger.register_unit(qis)

    print(f"\nQIS Created: {qis.symbol}")
    print(f"  Notional: $100,000")
    print(f"  Initial NAV: $100")
    print(f"  Target Leverage: 2x")
    print(f"  Funding Rate: 5% annual")
    print(f"  Rebalancing: Daily")

    # Strategy and contract
    strategy = leveraged_strategy("SPX", 2.0)
    contract = qis_contract(strategy)

    # Simulate a week of trading
    # SPX price path with realistic daily moves
    price_path = [
        (datetime(2025, 1, 1), 100.00),  # Day 0: Inception
        (datetime(2025, 1, 2), 101.50),  # Day 1: +1.5%
        (datetime(2025, 1, 3), 100.25),  # Day 2: -1.23%
        (datetime(2025, 1, 4), 102.00),  # Day 3: +1.75%
        (datetime(2025, 1, 5), 101.00),  # Day 4: -0.98%
        (datetime(2025, 1, 6), 103.50),  # Day 5: +2.48%
        (datetime(2025, 1, 7), 105.00),  # Day 6: +1.45%
        (datetime(2025, 1, 8), 105.00),  # Day 7: Maturity (no change)
    ]

    print("\n" + "-" * 70)
    print("DAILY SIMULATION")
    print("-" * 70)
    print(f"{'Day':<6} {'Date':<12} {'SPX Price':<12} {'NAV':<12} {'Leverage':<10} {'Return':<10}")
    print("-" * 70)

    spx_initial = price_path[0][1]

    for i, (ts, price) in enumerate(price_path):
        ledger.advance_time(ts)

        # Get state before
        if i > 0:
            nav = get_qis_nav(ledger, "QIS_2X_SPX", {"SPX": price})
            leverage = get_qis_leverage(ledger, "QIS_2X_SPX", {"SPX": price})
            qis_return = get_qis_return(ledger, "QIS_2X_SPX", {"SPX": price})
            spx_return = (price - spx_initial) / spx_initial

            print(f"Day {i:<3} {ts.strftime('%Y-%m-%d'):<12} ${price:<11.2f} ${nav:<11.2f} {leverage:<10.2f} {qis_return*100:>+7.2f}%")
        else:
            print(f"Day {i:<3} {ts.strftime('%Y-%m-%d'):<12} ${price:<11.2f} $100.00      2.00       +0.00%")

        # Execute lifecycle
        tx = contract(ledger, "QIS_2X_SPX", ts, {"SPX": price})
        if not tx.is_empty():
            ledger.execute(tx)

    # Final results
    final_state = ledger.get_unit_state("QIS_2X_SPX")
    spx_return = (price_path[-1][1] - spx_initial) / spx_initial

    print("-" * 70)
    print("\nFINAL RESULTS")
    print("-" * 70)
    print(f"SPX Return:      {spx_return*100:>+8.2f}%")
    print(f"2x ETF Return:   {final_state['final_return']*100:>+8.2f}%")
    print(f"Expected (2x):   {spx_return*2*100:>+8.2f}%")
    print(f"Tracking Error:  {(final_state['final_return'] - spx_return*2)*100:>+8.2f}%")
    print(f"\nFinal NAV:       ${final_state['final_nav']:.2f}")
    print(f"Initial NAV:     $100.00")

    # Settlement
    payoff = final_state['final_return'] * 100_000  # notional
    if payoff > 0:
        print(f"\nSettlement: Dealer pays Investor ${payoff:,.2f}")
    else:
        print(f"\nSettlement: Investor pays Dealer ${-payoff:,.2f}")

    print(f"\nPost-settlement balances:")
    print(f"  Dealer:   ${ledger.get_balance('dealer', 'USD'):,.2f}")
    print(f"  Investor: ${ledger.get_balance('investor', 'USD'):,.2f}")

    print("\n" + "=" * 70)
    print("KEY INSIGHTS")
    print("=" * 70)
    print("""
1. PATH DEPENDENCY: The 2x ETF return is NOT exactly 2x the SPX return.
   Daily rebalancing causes the returns to compound differently.

2. VOLATILITY DRAG: In volatile markets, the 2x ETF underperforms 2x
   the index return due to the "buy high, sell low" effect of rebalancing.

3. FINANCING COSTS: The borrowed funds (negative cash) accrue interest
   at the funding rate, creating a performance drag.

4. SELF-FINANCING: Each rebalance preserves NAV - no external cash flows.
   The only cash moves are at settlement.
""")


if __name__ == "__main__":
    main()
