"""
test_pricing_source.py - Unit tests for pricing_source.py

Tests:
- StaticPricingSource: static prices, updates
- TimeSeriesPricingSource: time-varying prices (incremental and batch initialization)
"""

import pytest
from datetime import datetime, timedelta
from ledger import (
    StaticPricingSource,
    TimeSeriesPricingSource,
)


class TestStaticPricingSource:
    """Tests for StaticPricingSource."""

    def test_create_static_source(self):
        source = StaticPricingSource({'AAPL': 175.0, 'TSLA': 250.0})
        assert source.base_currency == 'USD'

    def test_create_with_custom_base_currency(self):
        source = StaticPricingSource({'AAPL': 175.0}, base_currency='EUR')
        assert source.base_currency == 'EUR'

    def test_get_price(self):
        source = StaticPricingSource({'AAPL': 175.0, 'TSLA': 250.0})
        assert source.get_price('AAPL', datetime.now()) == 175.0
        assert source.get_price('TSLA', datetime.now()) == 250.0

    def test_get_price_base_currency(self):
        source = StaticPricingSource({'AAPL': 175.0})
        # Base currency always prices at 1.0
        assert source.get_price('USD', datetime.now()) == 1.0

    def test_get_price_unknown_unit(self):
        source = StaticPricingSource({'AAPL': 175.0})
        assert source.get_price('UNKNOWN', datetime.now()) is None

    def test_get_price_ignores_timestamp(self):
        source = StaticPricingSource({'AAPL': 175.0})
        t1 = datetime(2025, 1, 1)
        t2 = datetime(2025, 12, 31)
        assert source.get_price('AAPL', t1) == source.get_price('AAPL', t2)

    def test_get_prices_multiple(self):
        source = StaticPricingSource({'AAPL': 175.0, 'TSLA': 250.0, 'MSFT': 400.0})
        prices = source.get_prices({'AAPL', 'TSLA', 'UNKNOWN'}, datetime.now())
        assert prices == {'AAPL': 175.0, 'TSLA': 250.0}
        assert 'UNKNOWN' not in prices

    def test_update_price(self):
        source = StaticPricingSource({'AAPL': 175.0})
        source.update_price('AAPL', 180.0)
        assert source.get_price('AAPL', datetime.now()) == 180.0

    def test_update_prices(self):
        source = StaticPricingSource({'AAPL': 175.0})
        source.update_prices({'AAPL': 180.0, 'TSLA': 260.0})
        assert source.get_price('AAPL', datetime.now()) == 180.0
        assert source.get_price('TSLA', datetime.now()) == 260.0

    def test_repr(self):
        source = StaticPricingSource({'AAPL': 175.0, 'TSLA': 250.0})
        assert 'StaticPricingSource' in repr(source)


class TestTimeSeriesPricingSource:
    """Tests for TimeSeriesPricingSource."""

    def test_create_empty_source(self):
        source = TimeSeriesPricingSource()
        assert source.base_currency == 'USD'
        assert source.price_history == {}

    def test_add_price(self):
        source = TimeSeriesPricingSource()
        t = datetime(2025, 1, 15)
        source.add_price('AAPL', t, 175.0)
        assert source.get_price('AAPL', t) == 175.0

    def test_add_prices_multiple(self):
        source = TimeSeriesPricingSource()
        t = datetime(2025, 1, 15)
        source.add_prices({'AAPL': 175.0, 'TSLA': 250.0}, t)
        assert source.get_price('AAPL', t) == 175.0
        assert source.get_price('TSLA', t) == 250.0

    def test_get_price_uses_last_known(self):
        source = TimeSeriesPricingSource()
        source.add_price('AAPL', datetime(2025, 1, 15), 175.0)
        source.add_price('AAPL', datetime(2025, 1, 17), 180.0)

        # Query in between - should get price from 15th
        assert source.get_price('AAPL', datetime(2025, 1, 16)) == 175.0

        # Query after 17th - should get price from 17th
        assert source.get_price('AAPL', datetime(2025, 1, 20)) == 180.0

    def test_get_price_before_any_data(self):
        source = TimeSeriesPricingSource()
        source.add_price('AAPL', datetime(2025, 1, 15), 175.0)

        # Query before any data
        assert source.get_price('AAPL', datetime(2025, 1, 10)) is None

    def test_get_price_base_currency(self):
        source = TimeSeriesPricingSource()
        assert source.get_price('USD', datetime.now()) == 1.0

    def test_get_price_unknown_unit(self):
        source = TimeSeriesPricingSource()
        assert source.get_price('UNKNOWN', datetime.now()) is None

    def test_repr(self):
        source = TimeSeriesPricingSource()
        source.add_price('AAPL', datetime(2025, 1, 15), 175.0)
        source.add_price('AAPL', datetime(2025, 1, 16), 176.0)
        repr_str = repr(source)
        assert 'TimeSeriesPricingSource' in repr_str
        assert '1 units' in repr_str
        assert '2 observations' in repr_str


class TestTimeSeriesWithPaths:
    """Tests for TimeSeriesPricingSource with pre-populated paths."""

    def test_create_with_paths(self):
        t0 = datetime(2025, 1, 1)
        aapl_path = [
            (t0, 100.0),
            (t0 + timedelta(days=1), 101.0),
            (t0 + timedelta(days=2), 102.0),
        ]
        source = TimeSeriesPricingSource({'AAPL': aapl_path})
        assert source.get_price('AAPL', t0) == 100.0
        assert source.get_price('AAPL', t0 + timedelta(days=1)) == 101.0

    def test_get_price_uses_last_known(self):
        t0 = datetime(2025, 1, 1)
        aapl_path = [
            (t0, 100.0),
            (t0 + timedelta(days=2), 102.0),
        ]
        source = TimeSeriesPricingSource({'AAPL': aapl_path})

        # Query between points
        assert source.get_price('AAPL', t0 + timedelta(days=1)) == 100.0

    def test_get_price_before_path_start(self):
        t0 = datetime(2025, 1, 1)
        aapl_path = [(t0, 100.0)]
        source = TimeSeriesPricingSource({'AAPL': aapl_path})

        # Query before path
        assert source.get_price('AAPL', t0 - timedelta(days=1)) is None

    def test_get_price_base_currency(self):
        source = TimeSeriesPricingSource({})
        assert source.get_price('USD', datetime.now()) == 1.0

    def test_get_price_unknown_unit(self):
        source = TimeSeriesPricingSource({})
        assert source.get_price('UNKNOWN', datetime.now()) is None

    def test_get_all_timestamps_single_unit(self):
        t0 = datetime(2025, 1, 1)
        path = [
            (t0, 100.0),
            (t0 + timedelta(days=1), 101.0),
            (t0 + timedelta(days=2), 102.0),
        ]
        source = TimeSeriesPricingSource({'AAPL': path})

        timestamps = source.get_all_timestamps('AAPL')
        assert len(timestamps) == 3
        assert timestamps[0] == t0

    def test_get_all_timestamps_union(self):
        t0 = datetime(2025, 1, 1)
        aapl_path = [
            (t0, 100.0),
            (t0 + timedelta(days=2), 102.0),
        ]
        tsla_path = [
            (t0 + timedelta(days=1), 200.0),
            (t0 + timedelta(days=2), 205.0),
        ]
        source = TimeSeriesPricingSource({'AAPL': aapl_path, 'TSLA': tsla_path})

        timestamps = source.get_all_timestamps()
        assert len(timestamps) == 3  # Union of all timestamps

    def test_get_all_timestamps_unknown_unit(self):
        source = TimeSeriesPricingSource({})
        assert source.get_all_timestamps('UNKNOWN') == []

    def test_empty_path_ignored(self):
        source = TimeSeriesPricingSource({'AAPL': []})
        assert source.get_price('AAPL', datetime.now()) is None

    def test_paths_sorted(self):
        t0 = datetime(2025, 1, 1)
        # Provide out-of-order
        path = [
            (t0 + timedelta(days=2), 102.0),
            (t0, 100.0),
            (t0 + timedelta(days=1), 101.0),
        ]
        source = TimeSeriesPricingSource({'AAPL': path})

        timestamps = source.get_all_timestamps('AAPL')
        assert timestamps == sorted(timestamps)

    def test_repr(self):
        t0 = datetime(2025, 1, 1)
        path = [(t0, 100.0), (t0 + timedelta(days=1), 101.0)]
        source = TimeSeriesPricingSource({'AAPL': path, 'TSLA': path})
        repr_str = repr(source)
        assert 'TimeSeriesPricingSource' in repr_str


class TestPricingSourceIntegration:
    """Integration tests combining multiple pricing sources."""

    def test_simulation_workflow(self):
        """Simulate a typical Monte Carlo workflow."""
        t0 = datetime(2025, 1, 1)

        # Generate simulated price path
        prices = []
        price = 100.0
        for i in range(252):
            t = t0 + timedelta(days=i)
            prices.append((t, price))
            price *= 1.001  # Simple drift

        source = TimeSeriesPricingSource({'AAPL': prices})

        # Verify we can query at any point
        mid_price = source.get_price('AAPL', t0 + timedelta(days=126))
        assert mid_price is not None
        assert mid_price > 100.0

        # Get all timestamps
        timestamps = source.get_all_timestamps('AAPL')
        assert len(timestamps) == 252

    def test_historical_backtest_workflow(self):
        """Simulate historical backtesting."""
        source = TimeSeriesPricingSource()

        # Add historical data
        for day in range(30):
            t = datetime(2025, 1, 1) + timedelta(days=day)
            source.add_prices({
                'AAPL': 175.0 + day * 0.5,
                'TSLA': 250.0 - day * 0.3,
            }, t)

        # Query at different points in time
        early = source.get_prices({'AAPL', 'TSLA'}, datetime(2025, 1, 5))
        late = source.get_prices({'AAPL', 'TSLA'}, datetime(2025, 1, 25))

        # AAPL increased
        assert late['AAPL'] > early['AAPL']
        # TSLA decreased
        assert late['TSLA'] < early['TSLA']
