"""
option_example.py - Step-by-Step Bilateral Option Example

Demonstrates the complete lifecycle of a bilateral call option:
1. Setup: Create ledger, register assets, fund wallets
2. Option Creation: Define terms and register the option unit
3. Trade: Buyer pays premium and receives option contracts
4. Monitoring: Check positions, moneyness, intrinsic value
5. Settlement: Compute and execute physical delivery at maturity

This example shows both manual settlement (using compute_option_settlement)
and automatic settlement (using LifecycleEngine).

Run this file directly:
    python option_example.py
"""

from datetime import datetime
from ledger import (
    # Core
    Ledger, Move, cash, build_transaction, SYSTEM_WALLET,

    # Stock module
    create_stock_unit,

    # Options module
    create_option_unit,
    compute_option_settlement,
    get_option_intrinsic_value,
    option_contract,
    option_transact,

    # Engine
    LifecycleEngine,
)


def stock(symbol: str, name: str, issuer: str, shortable: bool = False):
    """Helper to create a simple stock unit."""
    return create_stock_unit(symbol, name, issuer, "USD", shortable=shortable)


def get_option_moneyness(ledger, option_symbol: str, spot_price: float) -> str:
    """Determine if option is ITM, ATM, or OTM."""
    state = ledger.get_unit_state(option_symbol)
    strike = state['strike']
    option_type = state['option_type']

    if option_type == 'call':
        if spot_price > strike:
            return 'ITM'
        elif spot_price < strike:
            return 'OTM'
        else:
            return 'ATM'
    else:  # put
        if spot_price < strike:
            return 'ITM'
        elif spot_price > strike:
            return 'OTM'
        else:
            return 'ATM'


def is_option_expired(ledger: Ledger, option_symbol: str) -> bool:
    """Check if option has reached maturity."""
    state = ledger.get_unit_state(option_symbol)
    maturity = state.get('maturity')
    return ledger.current_time >= maturity if maturity else False


def is_option_settled(ledger: Ledger, option_symbol: str) -> bool:
    """Check if option has been settled."""
    state = ledger.get_unit_state(option_symbol)
    return state.get('settled', False)


def summarize_option(ledger: Ledger, option_symbol: str) -> dict:
    """Get summary information about an option."""
    state = ledger.get_unit_state(option_symbol)
    return {
        'symbol': option_symbol,
        'underlying': state.get('underlying'),
        'strike': state.get('strike'),
        'maturity': state.get('maturity'),
        'option_type': state.get('option_type'),
        'quantity': state.get('quantity'),
        'currency': state.get('currency'),
        'long_wallet': state.get('long_wallet'),
        'short_wallet': state.get('short_wallet'),
        'settled': state.get('settled', False),
        'exercised': state.get('exercised', False),
        'settlement_price': state.get('settlement_price'),
    }


def main():
    print("=" * 70)
    print("BILATERAL CALL OPTION - COMPLETE LIFECYCLE EXAMPLE")
    print("=" * 70)

    # =========================================================================
    # STEP 1: SETUP
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 1: SETUP")
    print("=" * 70)
    print("""
    We create a ledger and register:
    - USD (cash for premium and strike payment)
    - AAPL (underlying stock for physical delivery)
    - Two wallets: Alice (buyer) and Bob (seller)
    """)

    ledger = Ledger(
        name="options_demo",
        initial_time=datetime(2025, 6, 1, 9, 30),  # June 1, 2025
        verbose=True,
    )

    # Register assets
    print("--- Registering Assets ---")
    ledger.register_unit(cash("USD", "US Dollar", decimal_places=2))
    ledger.register_unit(stock("AAPL", "Apple Inc.", issuer="AAPL", shortable=True))

    # Register wallets
    print("\n--- Registering Wallets ---")
    alice = ledger.register_wallet("alice")  # Option buyer
    bob = ledger.register_wallet("bob")      # Option seller (writer)
    mint = ledger.register_wallet("mint")    # Funding source

    # Fund wallets via SYSTEM_WALLET (proper issuance)
    print("\n--- Funding Wallets ---")
    print("Alice receives $100,000 cash (to pay premium and exercise)")
    print("Bob receives $10,000 cash and 500 AAPL shares (to deliver if exercised)")

    # SYSTEM_WALLET is auto-registered by the ledger
    funding_tx = build_transaction(ledger, [
        Move(100_000, "USD", SYSTEM_WALLET, alice, "fund_alice"),
        Move(10_000, "USD", SYSTEM_WALLET, bob, "fund_bob"),
        Move(500, "AAPL", SYSTEM_WALLET, bob, "fund_bob_shares"),
    ])
    ledger.execute(funding_tx)

    print("\n--- Initial Positions ---")
    print(f"Alice: ${ledger.get_balance(alice, 'USD'):,.2f} cash, "
          f"{ledger.get_balance(alice, 'AAPL')} AAPL")
    print(f"Bob:   ${ledger.get_balance(bob, 'USD'):,.2f} cash, "
          f"{ledger.get_balance(bob, 'AAPL')} AAPL")

    # =========================================================================
    # STEP 2: CREATE THE OPTION
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 2: CREATE THE OPTION")
    print("=" * 70)
    print("""
    We define a bilateral call option:
    - Underlying: AAPL
    - Strike: $150
    - Maturity: December 19, 2025
    - Quantity: 100 shares per contract
    - Buyer: Alice (has the right to buy)
    - Seller: Bob (has the obligation to sell)

    This is bilateral, meaning ONLY Alice and Bob can hold positions.
    No third-party transfers allowed.
    """)

    # Define option parameters
    underlying = "AAPL"
    strike = 150.0
    maturity = datetime(2025, 12, 19, 16, 0)  # Dec 19, 2025 at 4pm
    option_type = "call"
    quantity = 100  # 100 shares per contract
    currency = "USD"

    print("--- Option Terms ---")
    print(f"  Underlying:       {underlying}")
    print(f"  Strike:           ${strike}")
    print(f"  Maturity:         {maturity}")
    print(f"  Type:             {option_type.upper()}")
    print(f"  Contract Size:    {quantity} shares")
    print(f"  Currency:         {currency}")
    print(f"  Long (Buyer):     {alice}")
    print(f"  Short (Seller):   {bob}")

    # Create and register the option unit
    print("\n--- Registering Option Unit ---")
    option_unit = create_option_unit(
        symbol="AAPL_C150_DEC25",
        name="AAPL Call $150 Dec 2025",
        underlying=underlying,
        strike=strike,
        maturity=maturity,
        option_type=option_type,
        quantity=quantity,
        currency=currency,
        long_wallet=alice,
        short_wallet=bob,
    )
    ledger.register_unit(option_unit)

    # =========================================================================
    # STEP 3: EXECUTE THE TRADE
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 3: EXECUTE THE TRADE")
    print("=" * 70)
    print("""
    Alice buys 3 call option contracts from Bob.
    Premium: $12.50 per contract = $37.50 total

    The trade has two legs:
    1. Alice pays premium to Bob
    2. Bob delivers option contracts to Alice
    """)

    num_contracts = 3
    premium_per_contract = 12.50
    total_premium = num_contracts * premium_per_contract

    print(f"--- Trade Details ---")
    print(f"  Contracts:        {num_contracts}")
    print(f"  Premium/contract: ${premium_per_contract}")
    print(f"  Total premium:    ${total_premium}")

    # Build the trade (pure function - returns PendingTransaction)
    print("\n--- Building Trade (Pure Function) ---")
    trade_result = option_transact(
        view=ledger,
        symbol="AAPL_C150_DEC25",
        seller=bob,
        buyer=alice,
        qty=num_contracts,
        price=premium_per_contract,
    )

    print(f"PendingTransaction: {trade_result}")
    print("Moves:")
    for move in trade_result.moves:
        print(f"  {move}")

    # Execute the trade
    print("\n--- Executing Trade ---")
    ledger.execute(trade_result)

    print("\n--- Positions After Trade ---")
    print(f"Alice: {ledger.get_balance(alice, 'AAPL_C150_DEC25')} options, "
          f"${ledger.get_balance(alice, 'USD'):,.2f} cash")
    print(f"Bob:   {ledger.get_balance(bob, 'AAPL_C150_DEC25')} options, "
          f"${ledger.get_balance(bob, 'USD'):,.2f} cash")

    # =========================================================================
    # STEP 4: MONITOR THE OPTION
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 4: MONITOR THE OPTION")
    print("=" * 70)
    print("""
    We can check the option's status at any time using pure functions.
    Let's check moneyness and intrinsic value at different spot prices.
    """)

    # Check at current time (before expiry)
    print("--- Option Status ---")
    print(f"  Expired:  {is_option_expired(ledger, 'AAPL_C150_DEC25')}")
    print(f"  Settled:  {is_option_settled(ledger, 'AAPL_C150_DEC25')}")

    # Check moneyness at different prices
    print("\n--- Moneyness at Different Spot Prices ---")
    for spot in [140.0, 150.0, 160.0, 175.0]:
        moneyness = get_option_moneyness(ledger, "AAPL_C150_DEC25", spot)
        intrinsic = get_option_intrinsic_value(ledger, "AAPL_C150_DEC25", spot)
        print(f"  Spot ${spot:>6.2f}: {moneyness:>3}, "
              f"Intrinsic Value = ${intrinsic:,.2f} per contract")

    # Full summary
    print("\n--- Full Option Summary ---")
    summary = summarize_option(ledger, "AAPL_C150_DEC25")
    for key, value in summary.items():
        print(f"  {key}: {value}")

    # =========================================================================
    # STEP 5: ATTEMPT EARLY SETTLEMENT
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 5: ATTEMPT EARLY SETTLEMENT")
    print("=" * 70)
    print("""
    Options can only be settled at or after maturity. Attempting to settle
    before maturity returns an empty ContractResult.
    """)

    print(f"Current time: {ledger.current_time}")
    print(f"Maturity:     {maturity}")

    early_settlement = compute_option_settlement(
        view=ledger,
        option_symbol="AAPL_C150_DEC25",
        settlement_price=170.0
    )

    print(f"\nSettlement result: {early_settlement}")
    print(f"Is empty: {early_settlement.is_empty()}")
    print("(Empty because option hasn't matured yet)")

    # =========================================================================
    # STEP 6: ADVANCE TO MATURITY
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 6: ADVANCE TO MATURITY")
    print("=" * 70)
    print("""
    Fast-forward to December 19, 2025 (maturity date).
    AAPL is trading at $175 (ITM - above $150 strike).
    """)

    ledger.advance_time(datetime(2025, 12, 19, 16, 0))
    settlement_price = 175.0

    print(f"New time:         {ledger.current_time}")
    print(f"Settlement price: ${settlement_price}")
    print(f"Strike price:     ${strike}")
    print(f"Option is:        {'ITM' if settlement_price > strike else 'OTM'}")

    print(f"\n--- Status at Maturity ---")
    print(f"  Expired: {is_option_expired(ledger, 'AAPL_C150_DEC25')}")
    print(f"  Moneyness: {get_option_moneyness(ledger, 'AAPL_C150_DEC25', settlement_price)}")
    print(f"  Intrinsic: ${get_option_intrinsic_value(ledger, 'AAPL_C150_DEC25', settlement_price):,.2f} per contract")

    # =========================================================================
    # STEP 7: COMPUTE SETTLEMENT (Pure Function)
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 7: COMPUTE SETTLEMENT (Pure Function)")
    print("=" * 70)
    print("""
    compute_option_settlement() is a PURE function:
    - It reads the ledger state
    - It returns a ContractResult with the settlement moves
    - It does NOT modify anything

    For an ITM call with physical delivery:
    - Alice (buyer) pays: strike x quantity x contracts = $150 x 100 x 3 = $45,000
    - Bob (seller) delivers: 100 x 3 = 300 AAPL shares
    - Option positions close out
    """)

    settlement_result = compute_option_settlement(
        view=ledger,
        option_symbol="AAPL_C150_DEC25",
        settlement_price=settlement_price
    )

    print("--- Settlement ContractResult ---")
    print(f"Result: {settlement_result}")
    print(f"\nMoves ({len(settlement_result.moves)}):")
    for move in settlement_result.moves:
        print(f"  {move}")

    print(f"\nState Changes ({len(settlement_result.state_changes)}):")
    for sc in settlement_result.state_changes:
        print(f"  [{sc.unit}]:")
        changed = sc.changed_fields()
        for key, (old_val, new_val) in changed.items():
            print(f"    {key}: {old_val} -> {new_val}")

    # Verify ledger hasn't changed yet
    print("\n--- Ledger State (BEFORE execute) ---")
    print(f"Alice options: {ledger.get_balance(alice, 'AAPL_C150_DEC25')}")
    print(f"Option settled: {ledger.get_unit_state('AAPL_C150_DEC25').get('settled')}")
    print("(Nothing changed yet - pure function only computed the result)")

    # =========================================================================
    # STEP 8: EXECUTE SETTLEMENT
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 8: EXECUTE SETTLEMENT")
    print("=" * 70)
    print("""
    Now we execute the ContractResult to actually settle the option.
    This is the ONLY step that mutates the ledger.
    """)

    print("--- Executing Settlement ---")
    exec_result = ledger.execute(settlement_result)
    print(f"Execution result: {exec_result}")

    # =========================================================================
    # STEP 9: VERIFY FINAL STATE
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 9: VERIFY FINAL STATE")
    print("=" * 70)

    print("--- Final Positions ---")
    print(f"Alice:")
    print(f"  Options: {ledger.get_balance(alice, 'AAPL_C150_DEC25')}")
    print(f"  AAPL:    {ledger.get_balance(alice, 'AAPL')} shares")
    print(f"  USD:     ${ledger.get_balance(alice, 'USD'):,.2f}")

    print(f"\nBob:")
    print(f"  Options: {ledger.get_balance(bob, 'AAPL_C150_DEC25')}")
    print(f"  AAPL:    {ledger.get_balance(bob, 'AAPL')} shares")
    print(f"  USD:     ${ledger.get_balance(bob, 'USD'):,.2f}")

    # Check option state
    print("\n--- Option Lifecycle State ---")
    state = ledger.get_unit_state("AAPL_C150_DEC25")
    print(f"  Settled:          {state.get('settled')}")
    print(f"  Exercised:        {state.get('exercised')}")
    print(f"  Settlement Price: ${state.get('settlement_price')}")

    # =========================================================================
    # STEP 10: VERIFY THE MATH
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 10: VERIFY THE MATH")
    print("=" * 70)

    print("""
    Initial State:
      Alice: $100,000 cash, 0 AAPL
      Bob:   $10,000 cash, 500 AAPL

    After Trade (premium = $37.50):
      Alice: $99,962.50 cash, 0 AAPL, 3 options
      Bob:   $10,037.50 cash, 500 AAPL, -3 options

    After Settlement (ITM, strike = $150, 300 shares):
      Alice pays:    $150 x 300 = $45,000
      Alice receives: 300 AAPL shares

      Alice: $99,962.50 - $45,000 = $54,962.50 cash, 300 AAPL
      Bob:   $10,037.50 + $45,000 = $55,037.50 cash, 200 AAPL
    """)

    expected_alice_cash = 100_000 - 37.50 - 45_000
    expected_bob_cash = 10_000 + 37.50 + 45_000
    expected_alice_aapl = 300
    expected_bob_aapl = 500 - 300

    actual_alice_cash = ledger.get_balance(alice, "USD")
    actual_bob_cash = ledger.get_balance(bob, "USD")
    actual_alice_aapl = ledger.get_balance(alice, "AAPL")
    actual_bob_aapl = ledger.get_balance(bob, "AAPL")

    print("--- Verification ---")
    print(f"Alice cash:  expected ${expected_alice_cash:,.2f}, "
          f"actual ${actual_alice_cash:,.2f} "
          f"{'OK' if abs(expected_alice_cash - actual_alice_cash) < 0.01 else 'FAIL'}")
    print(f"Bob cash:    expected ${expected_bob_cash:,.2f}, "
          f"actual ${actual_bob_cash:,.2f} "
          f"{'OK' if abs(expected_bob_cash - actual_bob_cash) < 0.01 else 'FAIL'}")
    print(f"Alice AAPL:  expected {expected_alice_aapl}, "
          f"actual {actual_alice_aapl} "
          f"{'OK' if expected_alice_aapl == actual_alice_aapl else 'FAIL'}")
    print(f"Bob AAPL:    expected {expected_bob_aapl}, "
          f"actual {actual_bob_aapl} "
          f"{'OK' if expected_bob_aapl == actual_bob_aapl else 'FAIL'}")

    # P&L calculation
    print("\n--- P&L Analysis ---")
    # Alice's P&L: bought shares worth $175 for $150, paid $12.50 premium per contract
    alice_pnl_per_contract = (settlement_price - strike) * quantity - premium_per_contract
    alice_total_pnl = alice_pnl_per_contract * num_contracts
    print(f"Alice P&L per contract: (${settlement_price} - ${strike}) x {quantity} - ${premium_per_contract} = ${alice_pnl_per_contract:,.2f}")
    print(f"Alice total P&L: ${alice_pnl_per_contract:,.2f} x {num_contracts} = ${alice_total_pnl:,.2f}")

    # Bob's P&L is the opposite
    bob_total_pnl = -alice_total_pnl
    print(f"Bob total P&L: ${bob_total_pnl:,.2f}")

    print("\n" + "=" * 70)
    print("COMPLETE!")
    print("=" * 70)


def main_with_lifecycle_engine():
    """
    Demonstrates automatic settlement using LifecycleEngine.

    The LifecycleEngine automatically settles the option at maturity by
    calling the option_contract handler at each time step.
    """
    print("\n" + "=" * 70)
    print("BONUS: AUTOMATIC SETTLEMENT WITH LIFECYCLE ENGINE")
    print("=" * 70)
    print("""
    This example shows how LifecycleEngine automates option settlement.
    The engine calls check_lifecycle() at each step, which triggers
    settlement automatically when the option reaches maturity.
    """)

    # Quick setup
    ledger = Ledger("engine_demo", datetime(2025, 6, 1), verbose=False)
    ledger.register_unit(cash("USD", "US Dollar"))
    ledger.register_unit(stock("AAPL", "Apple Inc.", issuer="AAPL", shortable=True))

    alice = ledger.register_wallet("alice")
    bob = ledger.register_wallet("bob")
    # SYSTEM_WALLET is auto-registered by the ledger

    # Fund wallets via SYSTEM_WALLET
    funding_tx = build_transaction(ledger, [
        Move(100_000, "USD", SYSTEM_WALLET, alice, "fund_alice"),
        Move(10_000, "USD", SYSTEM_WALLET, bob, "fund_bob"),
        Move(500, "AAPL", SYSTEM_WALLET, bob, "fund_bob_shares"),
    ])
    ledger.execute(funding_tx)

    maturity = datetime(2025, 12, 19, 16, 0)
    ledger.register_unit(create_option_unit(
        symbol="AAPL_C150",
        name="AAPL Call 150",
        underlying="AAPL",
        strike=150.0,
        maturity=maturity,
        option_type="call",
        quantity=100,
        currency="USD",
        long_wallet=alice,
        short_wallet=bob,
    ))

    # Trade
    trade = option_transact(ledger, "AAPL_C150", bob, alice, 3, 12.50)
    ledger.execute(trade)

    print(f"After trade: Alice has {ledger.get_balance(alice, 'AAPL_C150')} options")

    # Create engine
    engine = LifecycleEngine(ledger)
    engine.register("BILATERAL_OPTION", option_contract)

    # Step to maturity
    print("\n--- Stepping Engine to Maturity ---")
    prices = {"AAPL": 175.0}  # ITM

    # Before maturity - no settlement
    engine.step(datetime(2025, 12, 18), prices)
    print(f"Dec 18: Option settled = {ledger.get_unit_state('AAPL_C150').get('settled')}")

    # At maturity - auto settlement!
    txs = engine.step(maturity, prices)
    print(f"Dec 19: Option settled = {ledger.get_unit_state('AAPL_C150').get('settled')}")
    print(f"        Transactions executed: {len(txs)}")

    print(f"\nFinal: Alice has {ledger.get_balance(alice, 'AAPL')} AAPL, "
          f"${ledger.get_balance(alice, 'USD'):,.2f} USD")


if __name__ == "__main__":
    main()
    main_with_lifecycle_engine()
