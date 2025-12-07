"""
future.py - Exchange-Traded Futures Contracts with Virtual Ledger Pattern

This module provides functions for creating and managing exchange-traded futures contracts.
Futures use the Virtual Ledger pattern to handle multiple intraday trades before EOD settlement.

Key Concepts:
1. Virtual Ledger: Trades update virtual_quantity and virtual_cash only (no real moves)
2. Daily Settlement: EOD variation margin based on mark-to-market settlement price
3. Expiry Settlement: Final cash settlement on contract expiration

Virtual Ledger State:
    virtual_quantity: Net contracts held (accumulated across all trades)
    virtual_cash: Cumulative trade cash (resets to negative of MTM value after EOD)
    last_settlement_price: Previous EOD settlement price
    intraday_postings: Cumulative intraday margin moves (absolute value, for reporting)

Settlement Pattern:
    Intraday trades:
        - Update virtual_quantity and virtual_cash only
        - No real moves (just state updates)

    EOD (DAILY_SETTLEMENT):
        - variation_margin = virtual_cash + (virtual_quantity × settlement_price × multiplier)
        - If variation_margin > 0: holder has PROFIT → clearinghouse pays holder
        - If variation_margin < 0: holder has LOSS → holder pays clearinghouse
        - Reset: virtual_cash = -(virtual_quantity × settlement_price × multiplier)
        - Reset: intraday_postings = 0.0

    Expiry:
        - Final variation margin using expiry settlement price
        - Close out virtual_quantity to zero

Note on Sign Convention:
    - Long position (qty > 0): price UP = profit, price DOWN = loss
    - Short position (qty < 0): price UP = loss, price DOWN = profit
    - Variation margin follows standard futures semantics: profit = receive cash

All functions take LedgerView (read-only) and return immutable results.
"""

from __future__ import annotations
from datetime import datetime
from typing import Dict, Any, List

from ..core import (
    LedgerView, Move, ContractResult, Unit,
    QUANTITY_EPSILON, UNIT_TYPE_FUTURE,
)


def create_future_unit(
    symbol: str,
    name: str,
    underlying: str,
    expiry: datetime,
    multiplier: float,
    settlement_currency: str,
    exchange: str,
    holder_wallet: str,
    clearinghouse_wallet: str,
) -> Unit:
    """
    Create an exchange-traded futures contract unit with virtual ledger.

    A futures contract is a standardized agreement to buy or sell an underlying
    asset at a future date. Unlike forwards, futures are exchange-traded with
    daily mark-to-market settlement through a clearinghouse.

    Args:
        symbol: Unique identifier for the futures contract (e.g., "ESZ24", "CLF25")
        name: Human-readable name for the contract
        underlying: Symbol of the underlying asset (e.g., "SPX", "WTI")
        expiry: Expiration date and time of the contract
        multiplier: Contract size (e.g., 50 for ES, 1000 for CL)
        settlement_currency: Currency for margin payments (e.g., "USD", "EUR", "JPY")
        exchange: Exchange name for settlement timing (e.g., "CME", "ICE")
        holder_wallet: Wallet holding the futures position
        clearinghouse_wallet: Clearinghouse wallet for margin settlements

    Returns:
        Unit: A futures contract unit with type "FUTURE" and virtual ledger state.
        The unit's _state contains:
        - underlying, expiry, multiplier, settlement_currency, exchange
        - holder_wallet, clearinghouse_wallet
        - virtual_quantity: Net contracts held (starts at 0.0)
        - virtual_cash: Cumulative trade cash (starts at 0.0)
        - last_settlement_price: Previous EOD settlement price (starts at 0.0)
        - intraday_postings: Intraday margin calls posted today (starts at 0.0)
        - settled: Whether contract has been settled at expiry

    Raises:
        ValueError: If multiplier is not positive, or if wallets are empty/identical.

    Example:
        # Create an ES futures contract (E-mini S&P 500)
        future = create_future_unit(
            symbol="ESZ24",
            name="E-mini S&P 500 Dec 2024",
            underlying="SPX",
            expiry=datetime(2024, 12, 20, 16, 0),
            multiplier=50.0,
            settlement_currency="USD",
            exchange="CME",
            holder_wallet="trader",
            clearinghouse_wallet="clearinghouse"
        )
        ledger.register_unit(future)
    """
    if multiplier <= 0:
        raise ValueError(f"multiplier must be positive, got {multiplier}")
    if not settlement_currency or not settlement_currency.strip():
        raise ValueError("settlement_currency cannot be empty")
    if not holder_wallet or not holder_wallet.strip():
        raise ValueError("holder_wallet cannot be empty")
    if not clearinghouse_wallet or not clearinghouse_wallet.strip():
        raise ValueError("clearinghouse_wallet cannot be empty")
    if holder_wallet == clearinghouse_wallet:
        raise ValueError("holder_wallet and clearinghouse_wallet must be different")

    return Unit(
        symbol=symbol,
        name=name,
        unit_type=UNIT_TYPE_FUTURE,
        min_balance=-1_000_000.0,  # Allow large positions
        max_balance=1_000_000.0,
        decimal_places=2,
        transfer_rule=None,  # Futures can trade freely on exchange
        _state={
            'underlying': underlying,
            'expiry': expiry,
            'multiplier': multiplier,
            'settlement_currency': settlement_currency,
            'exchange': exchange,
            'holder_wallet': holder_wallet,
            'clearinghouse_wallet': clearinghouse_wallet,
            # Virtual ledger state
            'virtual_quantity': 0.0,
            'virtual_cash': 0.0,
            'last_settlement_price': 0.0,
            'intraday_postings': 0.0,
            'settled': False,
        }
    )


def execute_futures_trade(
    view: LedgerView,
    future_symbol: str,
    quantity: float,
    price: float,
) -> ContractResult:
    """
    Execute a futures trade by updating the virtual ledger only (no real moves).

    This function updates virtual_quantity and virtual_cash to reflect a new trade.
    No actual margin moves occur until EOD settlement.

    Args:
        view: Read-only view of the ledger state
        future_symbol: Symbol of the futures contract
        quantity: Number of contracts traded (positive = buy, negative = sell)
        price: Trade price per unit of underlying

    Returns:
        ContractResult with state updates to virtual ledger fields.
        No moves are generated.

    Example:
        # Buy 10 ES contracts at 4500.00
        result = execute_futures_trade(ledger, "ESZ24", 10.0, 4500.00)
        ledger.execute_contract(result)
        # virtual_quantity: 0 → 10
        # virtual_cash: 0 → -2,250,000 (= -10 × 4500 × 50)

        # Later, sell 5 contracts at 4520.00
        result = execute_futures_trade(ledger, "ESZ24", -5.0, 4520.00)
        ledger.execute_contract(result)
        # virtual_quantity: 10 → 5
        # virtual_cash: -2,250,000 → -1,120,000 (= -2,250,000 + 5 × 4520 × 50)
    """
    if abs(quantity) < QUANTITY_EPSILON:
        raise ValueError(f"Trade quantity is effectively zero: {quantity}")

    state = view.get_unit_state(future_symbol)

    if state.get('settled', False):
        raise ValueError(f"Cannot trade settled future: {future_symbol}")

    multiplier = state['multiplier']
    current_virtual_quantity = state.get('virtual_quantity', 0.0)
    current_virtual_cash = state.get('virtual_cash', 0.0)

    # Update virtual ledger
    # Buy increases virtual_quantity and decreases virtual_cash
    # Sell decreases virtual_quantity and increases virtual_cash
    new_virtual_quantity = current_virtual_quantity + quantity
    trade_cash_flow = -quantity * price * multiplier
    new_virtual_cash = current_virtual_cash + trade_cash_flow

    # Create state updates
    state_updates = {
        future_symbol: {
            **state,
            'virtual_quantity': new_virtual_quantity,
            'virtual_cash': new_virtual_cash,
        }
    }

    return ContractResult(moves=(), state_updates=state_updates)


def compute_daily_settlement(
    view: LedgerView,
    future_symbol: str,
    settlement_price: float,
) -> ContractResult:
    """
    Compute EOD daily settlement with one real margin move.

    This is the core of the virtual ledger pattern. It:
    1. Calculates margin_call = virtual_cash + (virtual_quantity × settlement_price × multiplier)
    2. Generates ONE real margin move (positive = margin call, negative = margin return)
    3. Resets virtual_cash = -(virtual_quantity × settlement_price × multiplier)
    4. Resets intraday_postings = 0.0
    5. Updates last_settlement_price

    Args:
        view: Read-only view of the ledger state
        future_symbol: Symbol of the futures contract
        settlement_price: EOD settlement price for the underlying

    Returns:
        ContractResult with:
        - moves: Single margin move (if non-zero)
        - state_updates: Updated virtual ledger and settlement tracking

    Example:
        # After buying 10 ES at 4500, settlement at 4510
        result = compute_daily_settlement(ledger, "ESZ24", 4510.00)
        # margin_call = -2,250,000 + (10 × 4510 × 50) = 5,000
        # Move: clearinghouse → trader, USD, 5,000 (margin return)
        # virtual_cash reset: -(10 × 4510 × 50) = -2,255,000
    """
    if settlement_price <= 0:
        raise ValueError(f"settlement_price must be positive, got {settlement_price}")

    state = view.get_unit_state(future_symbol)

    if state.get('settled', False):
        return ContractResult()  # Already settled at expiry

    virtual_quantity = state.get('virtual_quantity', 0.0)
    virtual_cash = state.get('virtual_cash', 0.0)
    multiplier = state['multiplier']
    settlement_currency = state['settlement_currency']
    holder_wallet = state['holder_wallet']
    clearinghouse_wallet = state['clearinghouse_wallet']

    # Calculate variation margin
    # variation_margin = virtual_cash + (virtual_quantity × settlement_price × multiplier)
    # This represents the net P&L since the last settlement
    # Positive variation_margin = holder has PROFIT → clearinghouse pays holder
    # Negative variation_margin = holder has LOSS → holder pays clearinghouse
    mark_to_market_value = virtual_quantity * settlement_price * multiplier
    variation_margin = virtual_cash + mark_to_market_value

    moves: List[Move] = []

    # Generate variation margin move if non-negligible
    if abs(variation_margin) > QUANTITY_EPSILON:
        if variation_margin > 0:
            # Holder has profit - clearinghouse pays holder
            moves.append(Move(
                source=clearinghouse_wallet,
                dest=holder_wallet,
                unit=settlement_currency,
                quantity=variation_margin,
                contract_id=f'daily_settlement_{future_symbol}',
            ))
        else:
            # Holder has loss - holder pays clearinghouse
            moves.append(Move(
                source=holder_wallet,
                dest=clearinghouse_wallet,
                unit=settlement_currency,
                quantity=-variation_margin,
                contract_id=f'daily_settlement_{future_symbol}',
            ))

    # Reset virtual_cash to negative of current MTM value
    new_virtual_cash = -mark_to_market_value

    # Update state
    state_updates = {
        future_symbol: {
            **state,
            'virtual_cash': new_virtual_cash,
            'last_settlement_price': settlement_price,
            'intraday_postings': 0.0,  # Reset intraday margin calls
        }
    }

    return ContractResult(moves=tuple(moves), state_updates=state_updates)


def compute_intraday_margin(
    view: LedgerView,
    future_symbol: str,
    current_price: float,
) -> ContractResult:
    """
    Compute intraday margin call and mark position to market.

    This function calculates and posts an intraday margin call if the position
    has moved significantly. After posting margin, it resets virtual_cash to
    prevent double-counting when EOD settlement runs:
    - Posts variation margin move (same semantics as daily settlement)
    - Updates virtual_cash to mark position at current_price
    - Tracks cumulative margin posted in intraday_postings
    - Records last_intraday_price for audit trail

    The key difference from daily_settlement is that intraday_postings
    accumulates (for reporting) while daily settlement resets it to 0.

    Args:
        view: Read-only view of the ledger state
        future_symbol: Symbol of the futures contract
        current_price: Current intraday price for margin calculation

    Returns:
        ContractResult with margin move and updated state.

    Example:
        # After buying 10 ES at 4500, price drops to 4450 intraday
        result = compute_intraday_margin(ledger, "ESZ24", 4450.00)
        # variation_margin = -2,250,000 + (10 × 4450 × 50) = -25,000
        # Move: trader → clearinghouse, USD, 25,000 (margin call)
        # virtual_cash: -2,250,000 → -2,225,000 (reset to mark at 4450)
        # intraday_postings: 0 → 25,000
        # If EOD runs at same price 4450, variation_margin = 0 (no double-count)
    """
    if current_price <= 0:
        raise ValueError(f"current_price must be positive, got {current_price}")

    state = view.get_unit_state(future_symbol)

    if state.get('settled', False):
        return ContractResult()

    virtual_quantity = state.get('virtual_quantity', 0.0)
    virtual_cash = state.get('virtual_cash', 0.0)
    multiplier = state['multiplier']
    settlement_currency = state['settlement_currency']
    holder_wallet = state['holder_wallet']
    clearinghouse_wallet = state['clearinghouse_wallet']
    current_intraday_postings = state.get('intraday_postings', 0.0)

    # Calculate variation margin based on current price
    # Same semantics as daily settlement: positive = profit, negative = loss
    mark_to_market_value = virtual_quantity * current_price * multiplier
    variation_margin = virtual_cash + mark_to_market_value

    moves: List[Move] = []

    # Generate variation margin move if non-negligible
    if abs(variation_margin) > QUANTITY_EPSILON:
        if variation_margin > 0:
            # Holder has profit - clearinghouse pays holder
            moves.append(Move(
                source=clearinghouse_wallet,
                dest=holder_wallet,
                unit=settlement_currency,
                quantity=variation_margin,
                contract_id=f'intraday_margin_{future_symbol}',
            ))
        else:
            # Holder has loss - holder pays clearinghouse
            moves.append(Move(
                source=holder_wallet,
                dest=clearinghouse_wallet,
                unit=settlement_currency,
                quantity=-variation_margin,
                contract_id=f'intraday_margin_{future_symbol}',
            ))

    # Update intraday_postings for reporting and RESET virtual_cash to break-even
    # at the current price to prevent double-counting when EOD settlement runs.
    #
    # After posting margin, the position is "marked to market" at current_price.
    # The new virtual_cash represents the cost basis at this price:
    #   new_virtual_cash = -(virtual_quantity * current_price * multiplier)
    #
    # This ensures that if EOD settlement runs at the same price, variation_margin = 0.
    #
    # Only track margin POSTED (when variation_margin < 0, holder pays).
    # Margin RETURNED (when variation_margin > 0) should not be added to postings.
    margin_posted = -variation_margin if variation_margin < 0 else 0.0
    new_intraday_postings = current_intraday_postings + margin_posted
    new_virtual_cash = -(virtual_quantity * current_price * multiplier)

    state_updates = {
        future_symbol: {
            **state,
            'intraday_postings': new_intraday_postings,
            'virtual_cash': new_virtual_cash,
            'last_intraday_price': current_price,  # Track for audit trail
        }
    }

    return ContractResult(moves=tuple(moves), state_updates=state_updates)


def compute_expiry(
    view: LedgerView,
    future_symbol: str,
    expiry_settlement_price: float,
) -> ContractResult:
    """
    Compute final settlement at contract expiry.

    This function performs the final settlement when the futures contract expires:
    1. Calculates final margin call using expiry settlement price
    2. Generates final margin move
    3. Marks contract as settled
    4. Resets virtual_quantity to 0.0

    Args:
        view: Read-only view of the ledger state
        future_symbol: Symbol of the futures contract
        expiry_settlement_price: Final settlement price at expiry

    Returns:
        ContractResult with final margin move and settlement state update.

    Example:
        # At expiry, holding 10 ES bought at avg 4500, expiry settlement at 4550
        result = compute_expiry(ledger, "ESZ24", 4550.00)
        # Final margin_call = virtual_cash + (10 × 4550 × 50)
        # Move: final margin adjustment
        # Mark as settled, virtual_quantity → 0
    """
    if expiry_settlement_price <= 0:
        raise ValueError(f"expiry_settlement_price must be positive, got {expiry_settlement_price}")

    state = view.get_unit_state(future_symbol)

    if state.get('settled', False):
        return ContractResult()  # Already settled

    expiry = state['expiry']
    if view.current_time < expiry:
        return ContractResult()  # Not yet expired

    virtual_quantity = state.get('virtual_quantity', 0.0)
    virtual_cash = state.get('virtual_cash', 0.0)
    multiplier = state['multiplier']
    settlement_currency = state['settlement_currency']
    holder_wallet = state['holder_wallet']
    clearinghouse_wallet = state['clearinghouse_wallet']

    # Calculate final variation margin
    # Same semantics: positive = profit (clearinghouse pays), negative = loss (holder pays)
    mark_to_market_value = virtual_quantity * expiry_settlement_price * multiplier
    final_variation_margin = virtual_cash + mark_to_market_value

    moves: List[Move] = []

    # Generate final variation margin move if non-negligible
    if abs(final_variation_margin) > QUANTITY_EPSILON:
        if final_variation_margin > 0:
            # Holder has profit - clearinghouse pays holder
            moves.append(Move(
                source=clearinghouse_wallet,
                dest=holder_wallet,
                unit=settlement_currency,
                quantity=final_variation_margin,
                contract_id=f'expiry_settlement_{future_symbol}',
            ))
        else:
            # Holder has loss - holder pays clearinghouse
            moves.append(Move(
                source=holder_wallet,
                dest=clearinghouse_wallet,
                unit=settlement_currency,
                quantity=-final_variation_margin,
                contract_id=f'expiry_settlement_{future_symbol}',
            ))

    # Mark as settled and close out position
    state_updates = {
        future_symbol: {
            **state,
            'virtual_quantity': 0.0,
            'virtual_cash': 0.0,
            'last_settlement_price': expiry_settlement_price,
            'settled': True,
            'settlement_price': expiry_settlement_price,
        }
    }

    return ContractResult(moves=tuple(moves), state_updates=state_updates)


def transact(
    view: LedgerView,
    symbol: str,
    event_type: str,
    event_date: datetime,
    **kwargs
) -> ContractResult:
    """
    Generate moves and state updates for a futures lifecycle event.

    This is the unified entry point for all futures lifecycle events, routing
    to the appropriate handler based on event_type.

    Args:
        view: Read-only ledger access
        symbol: Futures contract symbol
        event_type: Type of event (DAILY_SETTLEMENT, EXPIRY, MARGIN_CALL, TRADE)
        event_date: When the event occurs
        **kwargs: Event-specific parameters:
            - For DAILY_SETTLEMENT: settlement_price (float, required)
            - For EXPIRY: expiry_settlement_price (float, required)
            - For MARGIN_CALL: current_price (float, required)
            - For TRADE: quantity (float, required), price (float, required)

    Returns:
        ContractResult with moves and state_updates, or empty result
        if event_type is unknown or required parameters are missing.

    Example:
        # Execute a trade
        result = transact(ledger, "ESZ24", "TRADE", datetime(2024, 11, 1),
                         quantity=10.0, price=4500.00)

        # Daily settlement
        result = transact(ledger, "ESZ24", "DAILY_SETTLEMENT", datetime(2024, 11, 1),
                         settlement_price=4510.00)

        # Intraday margin call
        result = transact(ledger, "ESZ24", "MARGIN_CALL", datetime(2024, 11, 1, 14, 30),
                         current_price=4450.00)

        # Expiry settlement
        result = transact(ledger, "ESZ24", "EXPIRY", datetime(2024, 12, 20),
                         expiry_settlement_price=4550.00)
    """
    if event_type == 'TRADE':
        quantity = kwargs.get('quantity')
        price = kwargs.get('price')
        if quantity is None or price is None:
            return ContractResult()
        return execute_futures_trade(view, symbol, quantity, price)

    elif event_type == 'DAILY_SETTLEMENT':
        settlement_price = kwargs.get('settlement_price')
        if settlement_price is None:
            return ContractResult()
        return compute_daily_settlement(view, symbol, settlement_price)

    elif event_type == 'MARGIN_CALL':
        current_price = kwargs.get('current_price')
        if current_price is None:
            return ContractResult()
        return compute_intraday_margin(view, symbol, current_price)

    elif event_type == 'EXPIRY':
        expiry_settlement_price = kwargs.get('expiry_settlement_price')
        if expiry_settlement_price is None:
            return ContractResult()
        return compute_expiry(view, symbol, expiry_settlement_price)

    else:
        return ContractResult()  # Unknown event type


def future_contract(
    view: LedgerView,
    symbol: str,
    timestamp: datetime,
    prices: Dict[str, float]
) -> ContractResult:
    """
    SmartContract function for automatic futures settlement.

    This function is called by the LifecycleEngine to automatically settle futures
    contracts. It checks if the contract has reached expiry and settles it using
    the provided market prices.

    Args:
        view: Read-only view of the ledger state
        symbol: Futures contract symbol
        timestamp: Current simulation time
        prices: Market prices dictionary (must contain underlying price)

    Returns:
        ContractResult with expiry settlement moves if conditions are met,
        empty otherwise.

    Example:
        # Register with LifecycleEngine
        engine = LifecycleEngine(ledger)
        engine.register("FUTURE", future_contract)

        # Engine will automatically settle at expiry
        timestamps = [datetime(2024, 12, i) for i in range(15, 25)]
        prices_func = lambda ts: {"SPX": 4550.00}
        engine.run(timestamps, prices_func)
    """
    state = view.get_unit_state(symbol)

    if state.get('settled', False):
        return ContractResult()

    expiry = state.get('expiry')
    if not expiry or timestamp < expiry:
        return ContractResult()

    underlying = state.get('underlying')
    expiry_settlement_price = prices.get(underlying)
    if expiry_settlement_price is None:
        return ContractResult()

    return compute_expiry(view, symbol, expiry_settlement_price)
