#!/usr/bin/env python3
"""
2x Leveraged SPX ETF Demo

This demonstrates a QIS (Quantitative Investment Strategy) that replicates
a 2x leveraged ETF with daily rebalancing.

Key concepts:
- Self-financing: NAV before rebalance = NAV after rebalance (no cash moves)
- Leverage via negative cash (notional borrowing)
- Daily rebalancing to maintain target leverage
- Financing costs on borrowed funds
- Volatility drag: 2x daily returns != 2x period return

Usage:
    python examples/qis_2x_leveraged_etf.py
"""

import sys
from pathlib import Path

# Add project root to path so we can import ledger
sys.path.insert(0, str(Path(__file__).parent.parent))

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

    # Create daily rebalance schedule for 10 days
    rebalance_dates = [inception + timedelta(days=i) for i in range(10)]
    maturity = inception + timedelta(days=10)

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

    # BUMPY price path to illustrate volatility drag
    # Market whipsaws: big up, big down, back to start
    price_path = [
        (datetime(2025, 1, 1),  100.00),   # Day 0: Inception
        (datetime(2025, 1, 2),  110.00),   # Day 1: +10% SHARP UP
        (datetime(2025, 1, 3),  100.00),   # Day 2: -9.09% SHARP DOWN (back to start)
        (datetime(2025, 1, 4),  108.00),   # Day 3: +8%
        (datetime(2025, 1, 5),   94.00),   # Day 4: -13% SHARP DOWN
        (datetime(2025, 1, 6),  104.00),   # Day 5: +10.6% SHARP UP
        (datetime(2025, 1, 7),   98.00),   # Day 6: -5.8%
        (datetime(2025, 1, 8),  102.00),   # Day 7: +4.1%
        (datetime(2025, 1, 9),   96.00),   # Day 8: -5.9%
        (datetime(2025, 1, 10), 100.00),   # Day 9: +4.2% (back to start!)
        (datetime(2025, 1, 11), 100.00),   # Day 10: Maturity (unchanged)
    ]

    print("\n" + "-" * 70)
    print("DAILY SIMULATION - VOLATILE MARKET")
    print("-" * 70)
    print(f"{'Day':<5} {'Date':<12} {'SPX':<8} {'Daily':<8} {'NAV':<10} {'ETF Ret':<10} {'Lvg':<6}")
    print("-" * 70)

    spx_initial = price_path[0][1]
    prev_price = spx_initial

    for i, (ts, price) in enumerate(price_path):
        ledger.advance_time(ts)

        daily_ret = (price - prev_price) / prev_price if i > 0 else 0
        prev_price = price

        # Get state before lifecycle execution
        if i > 0:
            nav = get_qis_nav(ledger, "QIS_2X_SPX", {"SPX": price})
            leverage = get_qis_leverage(ledger, "QIS_2X_SPX", {"SPX": price})
            qis_return = get_qis_return(ledger, "QIS_2X_SPX", {"SPX": price})

            print(f"Day {i:<3} {ts.strftime('%Y-%m-%d'):<12} ${price:<7.2f} {daily_ret*100:>+6.1f}%  ${nav:<9.2f} {qis_return*100:>+8.2f}%  {leverage:.2f}")
        else:
            print(f"Day {i:<3} {ts.strftime('%Y-%m-%d'):<12} ${price:<7.2f}    --    $100.00       0.00%  2.00")

        # Execute lifecycle (rebalance or settlement)
        tx = contract(ledger, "QIS_2X_SPX", ts, {"SPX": price})
        if not tx.is_empty():
            ledger.execute(tx)

    # Final results
    final_state = ledger.get_unit_state("QIS_2X_SPX")
    spx_return = (price_path[-1][1] - spx_initial) / spx_initial

    print("-" * 70)
    print("\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)
    print(f"\nSPX went: $100 -> $110 -> $100 -> ... -> $100 (FLAT over period)")
    print(f"\nSPX Return:       {spx_return*100:>+8.2f}%  (back to where it started)")
    print(f"2x ETF Return:    {final_state['final_return']*100:>+8.2f}%  (LOST MONEY despite flat SPX!)")
    print(f"Expected (2x):    {spx_return*2*100:>+8.2f}%")
    print(f"Volatility Drag:  {(final_state['final_return'] - spx_return*2)*100:>+8.2f}%")
    print(f"\nFinal NAV:        ${final_state['final_nav']:.2f}")
    print(f"Initial NAV:      $100.00")

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
1. VOLATILITY DRAG: Even though SPX returned to $100 (0% return),
   the 2x ETF LOST money! This is the "buy high, sell low" effect
   of daily rebalancing in volatile markets.

2. PATH DEPENDENCY: The 2x ETF return depends on the PATH, not just
   the endpoint. High volatility = more drag.

3. SELF-FINANCING: Notice that all rebalances have ZERO cash moves.
   The "cash" is just notional tracking of the hypothetical borrowing.
   Real cash only moves at SETTLEMENT.

4. FINANCING COSTS: The borrowed funds (negative cash) accrue interest,
   adding to the performance drag.

5. LEVERAGE DRIFT: Between rebalances, leverage drifts as prices move.
   After a big up day, leverage drops below 2x (need to buy more).
   After a big down day, leverage rises above 2x (need to sell).
""")


if __name__ == "__main__":
    main()
