"""
pricing_source.py - Pricing infrastructure for ledger valuation

Provides flexible pricing mechanisms for valuing units at specific timestamps.

Classes:
- PricingSource: Protocol defining the pricing interface
- StaticPricingSource: Time-independent prices
- TimeSeriesPricingSource: Time-varying prices with historical data

All prices are returned in a base currency (typically USD).
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, Set, Optional, List, Tuple, Protocol, runtime_checkable
from bisect import bisect_right


@runtime_checkable
class PricingSource(Protocol):
    """
    Protocol for pricing sources.

    A pricing source provides unit prices at specific timestamps,
    denominated in a base currency (typically USD).

    Implementations must provide get_price() and get_prices() methods.
    """
    base_currency: str

    def get_price(self, unit_symbol: str, timestamp: datetime) -> Optional[Decimal]:
        """Get the price of a single unit at a specific timestamp."""
        ...

    def get_prices(self, units: Set[str], timestamp: datetime) -> Dict[str, Decimal]:
        """Get prices for multiple units at a specific timestamp."""
        ...


class StaticPricingSource:
    """
    Pricing source with static prices (time-independent).

    Prices remain constant regardless of timestamp.
    The base currency always has a price of 1.0.
    """

    def __init__(self, prices: Dict[str, Decimal], base_currency: str = "USD"):
        """
        Initialize with a static price map.

        Args:
            prices: Dictionary mapping unit symbols to prices in base currency
            base_currency: The currency in which prices are quoted
        """
        self.base_currency = base_currency
        self.prices = prices.copy()
        # Base currency always prices at 1.0
        self.prices[base_currency] = Decimal("1.0")

    def get_price(self, unit_symbol: str, timestamp: datetime) -> Optional[Decimal]:
        """Get static price (timestamp is ignored)."""
        return self.prices.get(unit_symbol)

    def get_prices(self, units: Set[str], timestamp: datetime) -> Dict[str, Decimal]:
        """Get prices for multiple units at a specific timestamp."""
        return {unit: self.prices[unit] for unit in units if unit in self.prices}

    def update_price(self, unit_symbol: str, price: Decimal):
        """Update the price of a unit."""
        self.prices[unit_symbol] = price

    def update_prices(self, prices: Dict[str, Decimal]):
        """Update multiple prices at once."""
        self.prices.update(prices)

    def __repr__(self):
        return f"StaticPricingSource({len(self.prices)} prices, base={self.base_currency})"


class TimeSeriesPricingSource:
    """
    Pricing source with time-varying prices.

    Stores historical price data and supports point-in-time valuation.
    Uses the most recent price at or before the requested timestamp.

    Supports two initialization patterns:
    - Empty initialization for incremental price addition via add_price()
    - Batch initialization with complete price paths for simulations
    """

    def __init__(
        self,
        price_paths: Optional[Dict[str, List[Tuple[datetime, Decimal]]]] = None,
        base_currency: str = "USD"
    ):
        """
        Initialize pricing source.

        Args:
            price_paths: Optional dict mapping unit symbols to list of (timestamp, price) tuples.
                        If None, creates empty source.
            base_currency: Base currency for prices

        Examples:
            # Empty initialization
            pricer = TimeSeriesPricingSource()
            pricer.add_price('AAPL', datetime(2025, 1, 15), 175.0)

            # Batch initialization with price paths
            pricer = TimeSeriesPricingSource({
                'AAPL': [(t0, 100), (t1, 102), (t2, 101)],
                'TSLA': [(t0, 200), (t1, 205), (t2, 203)]
            })
        """
        self.base_currency = base_currency
        self.price_history: Dict[str, List[Tuple[datetime, Decimal]]] = {}

        if price_paths:
            for unit, path in price_paths.items():
                if not path:
                    continue
                # Sort by timestamp to ensure chronological order
                self.price_history[unit] = sorted(path, key=lambda x: x[0])

    def add_price(self, unit_symbol: str, timestamp: datetime, price: Decimal):
        """
        Add a price observation for a unit at a specific time.

        Args:
            unit_symbol: Unit symbol
            timestamp: Time of the price observation
            price: Price in base currency
        """
        if unit_symbol not in self.price_history:
            self.price_history[unit_symbol] = []

        # Insert in sorted order (by timestamp)
        self.price_history[unit_symbol].append((timestamp, price))
        self.price_history[unit_symbol].sort(key=lambda x: x[0])

    def add_prices(self, prices: Dict[str, Decimal], timestamp: datetime):
        """
        Add multiple price observations at the same timestamp.

        Args:
            prices: Dictionary mapping unit symbols to prices
            timestamp: Time of the observations
        """
        for unit, price in prices.items():
            self.add_price(unit, timestamp, price)

    def get_price(self, unit_symbol: str, timestamp: datetime) -> Optional[Decimal]:
        """
        Get price at or before the specified timestamp.

        Returns the most recent price at or before the requested time.
        Returns None if no price data is available before the timestamp.

        Uses binary search for efficient O(log n) lookup.
        """
        # Base currency always prices at 1.0
        if unit_symbol == self.base_currency:
            return Decimal("1.0")

        if unit_symbol not in self.price_history:
            return None

        history = self.price_history[unit_symbol]
        if not history:
            return None

        # Binary search: find rightmost entry with ts <= timestamp
        # Extract timestamps for bisect
        timestamps = [ts for ts, _ in history]
        idx = bisect_right(timestamps, timestamp)

        if idx == 0:
            # No price at or before timestamp
            return None

        # Return the price at index idx-1 (last entry <= timestamp)
        return history[idx - 1][1]

    def get_prices(self, units: Set[str], timestamp: datetime) -> Dict[str, Decimal]:
        """Get prices for multiple units at a specific timestamp."""
        prices = {}
        for unit in units:
            price = self.get_price(unit, timestamp)
            if price is not None:
                prices[unit] = price
        return prices

    def get_all_timestamps(self, unit_symbol: Optional[str] = None) -> List[datetime]:
        """
        Get all timestamps in the price history.

        Args:
            unit_symbol: If specified, get timestamps for that unit only.
                         If None, get union of all timestamps.

        Returns:
            Sorted list of unique timestamps
        """
        if unit_symbol:
            if unit_symbol in self.price_history:
                return [ts for ts, _ in self.price_history[unit_symbol]]
            return []

        # Get union of all timestamps
        all_times: Set[datetime] = set()
        for path in self.price_history.values():
            all_times.update(ts for ts, _ in path)

        return sorted(all_times)

    def __repr__(self):
        total_observations = sum(len(history) for history in self.price_history.values())
        return f"TimeSeriesPricingSource({len(self.price_history)} units, {total_observations} observations, base={self.base_currency})"
