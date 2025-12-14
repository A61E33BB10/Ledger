"""
lifecycle_load_example.py - LifecycleEngine Load Test

Demonstrates the system's ability to handle mass option expiry:
- 10,000 stocks as underlyings
- 1,000 wallets
- 100,000 bilateral options with random strikes (50-150)
- All options expire in 1 week
- StaticPricingSource with random prices (50-150)
- Measures time to expire all options via LifecycleEngine

Run:
    python lifecycle_load_example.py
"""

import random
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict

from ledger import (
    # Core
    Ledger, Move, build_transaction, SYSTEM_WALLET,
    Unit, UNIT_TYPE_CASH,

    # Stock
    create_stock_unit,

    # Options
    create_option_unit, option_contract, option_transact,

    # Engine
    LifecycleEngine,

    # Pricing
    StaticPricingSource,
)


def main():
    """Run the lifecycle engine load test."""
    print("=" * 70)
    print("    LIFECYCLE ENGINE LOAD TEST")
    print("=" * 70)

    # Configuration
    NUM_STOCKS = 10_000
    NUM_WALLETS = 1_000
    NUM_OPTIONS = 100_000
    STRIKE_MIN = 50
    STRIKE_MAX = 150
    PRICE_MIN = 50
    PRICE_MAX = 150
    SEED = 42

    random.seed(SEED)

    print(f"""
    Configuration:
      Stocks:       {NUM_STOCKS:,}
      Wallets:      {NUM_WALLETS:,}
      Options:      {NUM_OPTIONS:,}
      Strike range: ${STRIKE_MIN} - ${STRIKE_MAX}
      Price range:  ${PRICE_MIN} - ${PRICE_MAX}
      Seed:         {SEED}
    """)

    # Setup timing
    start_date = datetime(2025, 1, 6, 9, 30)
    maturity = start_date + timedelta(weeks=1)

    print(f"    Start:    {start_date}")
    print(f"    Maturity: {maturity}")
    print()

    # =========================================================================
    # PHASE 1: Create Ledger and Register Units
    # =========================================================================
    print("-" * 70)
    print("PHASE 1: Create Ledger and Register Units")
    print("-" * 70)

    t0 = time.time()

    ledger = Ledger(
        name="lifecycle_load_test",
        initial_time=start_date,
        verbose=False,
    )

    # Register USD
    usd = Unit(
        symbol="USD",
        name="US Dollar",
        unit_type=UNIT_TYPE_CASH,
        min_balance=Decimal("-1000000000000"),  # Allow large negative for SYSTEM
        max_balance=Decimal("Infinity"),
        decimal_places=2,
    )
    ledger.register_unit(usd)

    t1 = time.time()
    print(f"  Ledger created:    {(t1-t0)*1000:.1f}ms")

    # Register stocks
    t0 = time.time()
    stock_symbols = []
    for i in range(NUM_STOCKS):
        symbol = f"STK_{i:05d}"
        stock_symbols.append(symbol)
        stock = create_stock_unit(
            symbol=symbol,
            name=f"Stock {i}",
            issuer="treasury",
            currency="USD",
            shortable=True,  # Allow short positions for option delivery
        )
        ledger.register_unit(stock)

    t1 = time.time()
    print(f"  Stocks registered: {(t1-t0)*1000:.1f}ms ({NUM_STOCKS:,} stocks, {NUM_STOCKS/((t1-t0)*1000)*1000:,.0f}/s)")

    # =========================================================================
    # PHASE 2: Register Wallets
    # =========================================================================
    print("-" * 70)
    print("PHASE 2: Register Wallets")
    print("-" * 70)

    t0 = time.time()

    # Treasury for stock issuance
    ledger.register_wallet("treasury")

    wallet_names = []
    for i in range(NUM_WALLETS):
        wallet = f"wallet_{i:04d}"
        wallet_names.append(wallet)
        ledger.register_wallet(wallet)

    t1 = time.time()
    print(f"  Wallets registered: {(t1-t0)*1000:.1f}ms ({NUM_WALLETS:,} wallets)")

    # =========================================================================
    # PHASE 3: Fund Wallets
    # =========================================================================
    print("-" * 70)
    print("PHASE 3: Fund Wallets (Initial Issuance)")
    print("-" * 70)

    t0 = time.time()

    # Fund treasury with all stocks
    treasury_funding_moves = []
    for symbol in stock_symbols:
        treasury_funding_moves.append(Move(
            Decimal("10000000"),  # 10M shares per stock
            symbol,
            SYSTEM_WALLET,
            "treasury",
            f"issue_{symbol}",
        ))

    # Batch the treasury funding (split into chunks to avoid too many moves per tx)
    BATCH_SIZE = 1000
    for i in range(0, len(treasury_funding_moves), BATCH_SIZE):
        batch = treasury_funding_moves[i:i+BATCH_SIZE]
        tx = build_transaction(ledger, batch)
        ledger.execute(tx)

    t1 = time.time()
    print(f"  Treasury funded:   {(t1-t0)*1000:.1f}ms ({NUM_STOCKS:,} stock positions)")

    # Fund wallets with USD and some stocks
    t0 = time.time()
    for wallet in wallet_names:
        # Give each wallet $10M and 1000 shares of 10 random stocks
        moves = [Move(Decimal("10000000"), "USD", SYSTEM_WALLET, wallet, f"fund_{wallet}_usd")]

        # Give shares of a subset of stocks
        assigned_stocks = random.sample(stock_symbols, min(10, NUM_STOCKS))
        for stock_sym in assigned_stocks:
            moves.append(Move(
                Decimal("1000"),
                stock_sym,
                "treasury",
                wallet,
                f"fund_{wallet}_{stock_sym}",
            ))

        tx = build_transaction(ledger, moves)
        ledger.execute(tx)

    t1 = time.time()
    print(f"  Wallets funded:    {(t1-t0)*1000:.1f}ms ({NUM_WALLETS:,} wallets)")

    # =========================================================================
    # PHASE 4: Create Options
    # =========================================================================
    print("-" * 70)
    print("PHASE 4: Create Bilateral Options")
    print("-" * 70)

    t0 = time.time()

    option_symbols = []
    option_underlyings = []  # Track which underlying each option uses

    for i in range(NUM_OPTIONS):
        # Random underlying
        underlying = random.choice(stock_symbols)

        # Random strike between 50-150
        strike = Decimal(str(random.randint(STRIKE_MIN, STRIKE_MAX)))

        # Random option type
        opt_type = random.choice(["call", "put"])

        # Random long/short wallets (different wallets)
        long_wallet = random.choice(wallet_names)
        short_wallet = random.choice(wallet_names)
        while short_wallet == long_wallet:
            short_wallet = random.choice(wallet_names)

        # Create option
        symbol = f"OPT_{i:06d}"
        option_symbols.append(symbol)
        option_underlyings.append(underlying)

        option = create_option_unit(
            symbol=symbol,
            name=f"Option {i}",
            underlying=underlying,
            strike=strike,
            maturity=maturity,
            option_type=opt_type,
            quantity=Decimal("100"),  # 100 shares per contract
            currency="USD",
            long_wallet=long_wallet,
            short_wallet=short_wallet,
        )
        ledger.register_unit(option)

    t1 = time.time()
    print(f"  Options created:   {(t1-t0)*1000:.1f}ms ({NUM_OPTIONS:,} options, {NUM_OPTIONS/((t1-t0)*1000)*1000:,.0f}/s)")

    # Issue option positions using option_transact
    # The short wallet "sells" to the long wallet with 0 premium (issuance)
    # This creates +1 for long, -1 for short (conservation: sum = 0)
    t0 = time.time()
    issued_count = 0

    for opt_sym in option_symbols:
        state = ledger.get_unit_state(opt_sym)
        long_wallet = state['long_wallet']
        short_wallet = state['short_wallet']

        # Use option_transact: seller (short) sells to buyer (long)
        # Price = 0 means pure issuance without premium exchange
        trade = option_transact(
            ledger,
            symbol=opt_sym,
            seller=short_wallet,
            buyer=long_wallet,
            qty=Decimal("1"),
            price=Decimal("0"),  # No premium for issuance
        )
        ledger.execute(trade)
        issued_count += 1

    t1 = time.time()
    print(f"  Options issued:    {(t1-t0)*1000:.1f}ms ({issued_count:,} positions)")

    # =========================================================================
    # PHASE 5: Create Static Pricing Source
    # =========================================================================
    print("-" * 70)
    print("PHASE 5: Create Static Pricing Source")
    print("-" * 70)

    t0 = time.time()

    # Generate random prices for all stocks
    prices: Dict[str, Decimal] = {}
    for symbol in stock_symbols:
        price = Decimal(str(random.randint(PRICE_MIN, PRICE_MAX)))
        prices[symbol] = price

    pricing_source = StaticPricingSource(prices, base_currency="USD")

    t1 = time.time()
    print(f"  Prices generated:  {(t1-t0)*1000:.1f}ms ({NUM_STOCKS:,} prices)")

    # Calculate how many options are ITM
    itm_calls = 0
    itm_puts = 0
    otm_count = 0

    for opt_sym in option_symbols:
        state = ledger.get_unit_state(opt_sym)
        underlying = state['underlying']
        strike = state['strike']
        opt_type = state['option_type']
        spot = prices.get(underlying, Decimal("100"))

        if opt_type == 'call':
            if spot > strike:
                itm_calls += 1
            else:
                otm_count += 1
        else:
            if spot < strike:
                itm_puts += 1
            else:
                otm_count += 1

    print(f"  ITM Calls:         {itm_calls:,}")
    print(f"  ITM Puts:          {itm_puts:,}")
    print(f"  OTM Options:       {otm_count:,}")

    # =========================================================================
    # PHASE 6: Setup LifecycleEngine
    # =========================================================================
    print("-" * 70)
    print("PHASE 6: Setup LifecycleEngine")
    print("-" * 70)

    t0 = time.time()

    engine = LifecycleEngine(ledger)
    engine.register("BILATERAL_OPTION", option_contract)

    t1 = time.time()
    print(f"  Engine setup:      {(t1-t0)*1000:.1f}ms")
    print(f"  Registered units:  {len(ledger.units):,}")
    print(f"  Transaction log:   {len(ledger.transaction_log):,} entries")

    # =========================================================================
    # PHASE 7: Advance Time and Run LifecycleEngine
    # =========================================================================
    print("-" * 70)
    print("PHASE 7: Run LifecycleEngine at Maturity")
    print("-" * 70)

    print(f"  Advancing time to: {maturity}")
    print(f"  Options to settle: {NUM_OPTIONS:,}")
    print()
    print("  Running lifecycle engine...")

    # Build price function
    def price_fn(t: datetime) -> Dict[str, Decimal]:
        return pricing_source.get_prices(set(stock_symbols), t)

    # Run the engine at maturity
    t0 = time.time()
    transactions = engine.step(maturity, price_fn(maturity))
    t1 = time.time()

    elapsed_ms = (t1 - t0) * 1000

    print(f"""
  RESULTS:
  --------
  Time elapsed:        {elapsed_ms:.1f}ms
  Transactions:        {len(transactions):,}
  Throughput:          {len(transactions)/(elapsed_ms/1000):,.0f} settlements/s
    """)

    # =========================================================================
    # PHASE 8: Verify Settlement
    # =========================================================================
    print("-" * 70)
    print("PHASE 8: Verify Settlement")
    print("-" * 70)

    t0 = time.time()

    settled_count = 0
    unsettled_count = 0

    # Sample check (check first 1000)
    sample_size = min(1000, NUM_OPTIONS)
    for opt_sym in option_symbols[:sample_size]:
        state = ledger.get_unit_state(opt_sym)
        if state.get('settled'):
            settled_count += 1
        else:
            unsettled_count += 1

    t1 = time.time()

    print(f"  Sampled:           {sample_size:,} options")
    print(f"  Settled:           {settled_count:,}")
    print(f"  Unsettled:         {unsettled_count:,}")
    print(f"  Verification time: {(t1-t0)*1000:.1f}ms")

    # Extrapolate
    if sample_size < NUM_OPTIONS:
        est_settled = int(settled_count / sample_size * NUM_OPTIONS)
        print(f"  Estimated total:   {est_settled:,} settled")

    # =========================================================================
    # PHASE 9: Conservation Check
    # =========================================================================
    print("-" * 70)
    print("PHASE 9: Conservation Check")
    print("-" * 70)

    t0 = time.time()

    # Check USD conservation
    usd_total = ledger.total_supply("USD")

    # Sample stock conservation
    violations = 0
    sample_stocks = random.sample(stock_symbols, min(100, NUM_STOCKS))
    for sym in sample_stocks:
        total = ledger.total_supply(sym)
        if abs(total) > Decimal("1e-6"):
            violations += 1

    t1 = time.time()

    print(f"  USD total supply:  {usd_total} (should be 0)")
    print(f"  Stock violations:  {violations} / {len(sample_stocks)} sampled")
    print(f"  Check time:        {(t1-t0)*1000:.1f}ms")

    if violations == 0 and abs(usd_total) < Decimal("1e-6"):
        print(f"  Status:            CONSERVATION VERIFIED")
    else:
        print(f"  Status:            CONSERVATION VIOLATION!")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print()
    print("=" * 70)
    print("    SUMMARY")
    print("=" * 70)
    print(f"""
    Load Test Configuration:
      - {NUM_STOCKS:,} stocks registered
      - {NUM_WALLETS:,} wallets registered
      - {NUM_OPTIONS:,} bilateral options created

    Settlement Performance:
      - Time: {elapsed_ms:.1f}ms
      - Rate: {len(transactions)/(elapsed_ms/1000):,.0f} settlements/second

    Final State:
      - Transaction log: {len(ledger.transaction_log):,} entries
      - Conservation: {"VERIFIED" if violations == 0 else "VIOLATION"}
    """)

    return elapsed_ms


if __name__ == "__main__":
    main()
