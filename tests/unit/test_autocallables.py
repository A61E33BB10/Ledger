"""
test_autocallables.py - Unit tests for autocallable structured products

Tests:
- Factory function (create_autocallable)
- Observation with autocall triggered
- Observation with coupon paid (above coupon barrier)
- Observation with coupon missed (below coupon barrier)
- Memory coupon accumulation over multiple periods
- Memory coupon payout on subsequent observation
- Put barrier knock-in
- Maturity with put knocked in (reduced payout)
- Maturity without knock-in (full principal)
- Full lifecycle with multiple observations
- Edge cases (barriers at exact levels)
- Already autocalled state
- Conservation laws
- transact() interface
- autocallable_contract() SmartContract
"""

import pytest
from datetime import datetime
from decimal import Decimal
from tests.fake_view import FakeView
from ledger import (
    create_autocallable,
    compute_observation,
    compute_maturity_payoff,
    autocallable_transact,
    autocallable_contract,
    get_autocallable_status,
    get_total_coupons_paid,
    UNIT_TYPE_AUTOCALLABLE,
)
from ledger.units.autocallable import _process_lifecycle_event as autocallable_lifecycle_event


# ============================================================================
# FACTORY TESTS
# ============================================================================

class TestCreateAutocallable:
    """Tests for create_autocallable factory function."""

    def test_create_basic_autocallable(self):
        """Create a basic autocallable with valid parameters."""
        unit = create_autocallable(
            symbol="AUTO_SPX_2025",
            name="SPX Autocallable 8% 2025",
            underlying="SPX",
            notional=100000.0,
            initial_spot=4500.0,
            autocall_barrier=1.0,
            coupon_barrier=0.7,
            coupon_rate=0.08,
            put_barrier=0.6,
            issue_date=datetime(2024, 1, 15),
            maturity_date=datetime(2025, 1, 15),
            observation_schedule=[
                datetime(2024, 4, 15),
                datetime(2024, 7, 15),
                datetime(2024, 10, 15),
                datetime(2025, 1, 15),
            ],
            currency="USD",
            issuer_wallet="bank",
            holder_wallet="investor",
            memory_feature=True,
        )

        assert unit.symbol == "AUTO_SPX_2025"
        assert unit.name == "SPX Autocallable 8% 2025"
        assert unit.unit_type == UNIT_TYPE_AUTOCALLABLE
        assert unit.state['underlying'] == "SPX"
        assert unit.state['notional'] == 100000.0
        assert unit.state['initial_spot'] == 4500.0
        assert unit.state['autocall_barrier'] == 1.0
        assert unit.state['coupon_barrier'] == 0.7
        assert unit.state['coupon_rate'] == 0.08
        assert unit.state['put_barrier'] == 0.6
        assert unit.state['memory_feature'] is True
        assert unit.state['autocalled'] is False
        assert unit.state['put_knocked_in'] is False
        assert unit.state['settled'] is False

    def test_create_autocallable_without_memory(self):
        """Create autocallable without memory feature."""
        unit = create_autocallable(
            symbol="AUTO_SPX_2025",
            name="SPX Autocallable 8% 2025",
            underlying="SPX",
            notional=100000.0,
            initial_spot=4500.0,
            autocall_barrier=1.0,
            coupon_barrier=0.7,
            coupon_rate=0.08,
            put_barrier=0.6,
            issue_date=datetime(2024, 1, 15),
            maturity_date=datetime(2025, 1, 15),
            observation_schedule=[datetime(2024, 4, 15)],
            currency="USD",
            issuer_wallet="bank",
            holder_wallet="investor",
            memory_feature=False,
        )

        assert unit.state['memory_feature'] is False

    def test_observation_schedule_sorted(self):
        """Observation schedule should be sorted."""
        unit = create_autocallable(
            symbol="AUTO_SPX_2025",
            name="SPX Autocallable",
            underlying="SPX",
            notional=100000.0,
            initial_spot=4500.0,
            autocall_barrier=1.0,
            coupon_barrier=0.7,
            coupon_rate=0.08,
            put_barrier=0.6,
            issue_date=datetime(2024, 1, 15),
            maturity_date=datetime(2025, 1, 15),
            observation_schedule=[
                datetime(2024, 10, 15),
                datetime(2024, 4, 15),
                datetime(2024, 7, 15),
            ],
            currency="USD",
            issuer_wallet="bank",
            holder_wallet="investor",
        )

        schedule = unit.state['observation_schedule']
        assert schedule[0] == datetime(2024, 4, 15)
        assert schedule[1] == datetime(2024, 7, 15)
        assert schedule[2] == datetime(2024, 10, 15)

    def test_validate_notional_positive(self):
        """Notional must be positive."""
        with pytest.raises(ValueError, match="notional must be positive"):
            create_autocallable(
                symbol="AUTO", name="Test", underlying="SPX",
                notional=0.0,  # Invalid
                initial_spot=100.0, autocall_barrier=1.0, coupon_barrier=0.7,
                coupon_rate=0.08, put_barrier=0.6,
                issue_date=datetime(2024, 1, 1), maturity_date=datetime(2025, 1, 1),
                observation_schedule=[datetime(2024, 6, 1)],
                currency="USD", issuer_wallet="bank", holder_wallet="investor",
            )

    def test_validate_initial_spot_positive(self):
        """Initial spot must be positive."""
        with pytest.raises(ValueError, match="initial_spot must be positive"):
            create_autocallable(
                symbol="AUTO", name="Test", underlying="SPX",
                notional=100000.0, initial_spot=-100.0,  # Invalid
                autocall_barrier=1.0, coupon_barrier=0.7,
                coupon_rate=0.08, put_barrier=0.6,
                issue_date=datetime(2024, 1, 1), maturity_date=datetime(2025, 1, 1),
                observation_schedule=[datetime(2024, 6, 1)],
                currency="USD", issuer_wallet="bank", holder_wallet="investor",
            )

    def test_validate_autocall_barrier_positive(self):
        """Autocall barrier must be positive."""
        with pytest.raises(ValueError, match="autocall_barrier must be positive"):
            create_autocallable(
                symbol="AUTO", name="Test", underlying="SPX",
                notional=100000.0, initial_spot=100.0,
                autocall_barrier=0.0,  # Invalid
                coupon_barrier=0.7, coupon_rate=0.08, put_barrier=0.6,
                issue_date=datetime(2024, 1, 1), maturity_date=datetime(2025, 1, 1),
                observation_schedule=[datetime(2024, 6, 1)],
                currency="USD", issuer_wallet="bank", holder_wallet="investor",
            )

    def test_validate_coupon_barrier_positive(self):
        """Coupon barrier must be positive."""
        with pytest.raises(ValueError, match="coupon_barrier must be positive"):
            create_autocallable(
                symbol="AUTO", name="Test", underlying="SPX",
                notional=100000.0, initial_spot=100.0,
                autocall_barrier=1.0, coupon_barrier=-0.5,  # Invalid
                coupon_rate=0.08, put_barrier=0.6,
                issue_date=datetime(2024, 1, 1), maturity_date=datetime(2025, 1, 1),
                observation_schedule=[datetime(2024, 6, 1)],
                currency="USD", issuer_wallet="bank", holder_wallet="investor",
            )

    def test_validate_put_barrier_positive(self):
        """Put barrier must be positive."""
        with pytest.raises(ValueError, match="put_barrier must be positive"):
            create_autocallable(
                symbol="AUTO", name="Test", underlying="SPX",
                notional=100000.0, initial_spot=100.0,
                autocall_barrier=1.0, coupon_barrier=0.7,
                coupon_rate=0.08, put_barrier=0.0,  # Invalid
                issue_date=datetime(2024, 1, 1), maturity_date=datetime(2025, 1, 1),
                observation_schedule=[datetime(2024, 6, 1)],
                currency="USD", issuer_wallet="bank", holder_wallet="investor",
            )

    def test_validate_coupon_rate_non_negative(self):
        """Coupon rate cannot be negative."""
        with pytest.raises(ValueError, match="coupon_rate cannot be negative"):
            create_autocallable(
                symbol="AUTO", name="Test", underlying="SPX",
                notional=100000.0, initial_spot=100.0,
                autocall_barrier=1.0, coupon_barrier=0.7,
                coupon_rate=-0.05,  # Invalid
                put_barrier=0.6,
                issue_date=datetime(2024, 1, 1), maturity_date=datetime(2025, 1, 1),
                observation_schedule=[datetime(2024, 6, 1)],
                currency="USD", issuer_wallet="bank", holder_wallet="investor",
            )

    def test_validate_issuer_wallet_not_empty(self):
        """Issuer wallet cannot be empty."""
        with pytest.raises(ValueError, match="issuer_wallet cannot be empty"):
            create_autocallable(
                symbol="AUTO", name="Test", underlying="SPX",
                notional=100000.0, initial_spot=100.0,
                autocall_barrier=1.0, coupon_barrier=0.7,
                coupon_rate=0.08, put_barrier=0.6,
                issue_date=datetime(2024, 1, 1), maturity_date=datetime(2025, 1, 1),
                observation_schedule=[datetime(2024, 6, 1)],
                currency="USD", issuer_wallet="",  # Invalid
                holder_wallet="investor",
            )

    def test_validate_holder_wallet_not_empty(self):
        """Holder wallet cannot be empty."""
        with pytest.raises(ValueError, match="holder_wallet cannot be empty"):
            create_autocallable(
                symbol="AUTO", name="Test", underlying="SPX",
                notional=100000.0, initial_spot=100.0,
                autocall_barrier=1.0, coupon_barrier=0.7,
                coupon_rate=0.08, put_barrier=0.6,
                issue_date=datetime(2024, 1, 1), maturity_date=datetime(2025, 1, 1),
                observation_schedule=[datetime(2024, 6, 1)],
                currency="USD", issuer_wallet="bank",
                holder_wallet="   ",  # Invalid (whitespace only)
            )

    def test_validate_wallets_different(self):
        """Issuer and holder wallets must be different."""
        with pytest.raises(ValueError, match="issuer_wallet and holder_wallet must be different"):
            create_autocallable(
                symbol="AUTO", name="Test", underlying="SPX",
                notional=100000.0, initial_spot=100.0,
                autocall_barrier=1.0, coupon_barrier=0.7,
                coupon_rate=0.08, put_barrier=0.6,
                issue_date=datetime(2024, 1, 1), maturity_date=datetime(2025, 1, 1),
                observation_schedule=[datetime(2024, 6, 1)],
                currency="USD", issuer_wallet="same", holder_wallet="same",
            )

    def test_validate_currency_not_empty(self):
        """Currency cannot be empty."""
        with pytest.raises(ValueError, match="currency cannot be empty"):
            create_autocallable(
                symbol="AUTO", name="Test", underlying="SPX",
                notional=100000.0, initial_spot=100.0,
                autocall_barrier=1.0, coupon_barrier=0.7,
                coupon_rate=0.08, put_barrier=0.6,
                issue_date=datetime(2024, 1, 1), maturity_date=datetime(2025, 1, 1),
                observation_schedule=[datetime(2024, 6, 1)],
                currency="",  # Invalid
                issuer_wallet="bank", holder_wallet="investor",
            )

    def test_validate_maturity_after_issue(self):
        """Maturity must be after issue date."""
        with pytest.raises(ValueError, match="maturity_date must be after issue_date"):
            create_autocallable(
                symbol="AUTO", name="Test", underlying="SPX",
                notional=100000.0, initial_spot=100.0,
                autocall_barrier=1.0, coupon_barrier=0.7,
                coupon_rate=0.08, put_barrier=0.6,
                issue_date=datetime(2025, 1, 1),
                maturity_date=datetime(2024, 1, 1),  # Invalid
                observation_schedule=[datetime(2024, 6, 1)],
                currency="USD", issuer_wallet="bank", holder_wallet="investor",
            )

    def test_validate_observation_schedule_not_empty(self):
        """Observation schedule cannot be empty."""
        with pytest.raises(ValueError, match="observation_schedule cannot be empty"):
            create_autocallable(
                symbol="AUTO", name="Test", underlying="SPX",
                notional=100000.0, initial_spot=100.0,
                autocall_barrier=1.0, coupon_barrier=0.7,
                coupon_rate=0.08, put_barrier=0.6,
                issue_date=datetime(2024, 1, 1), maturity_date=datetime(2025, 1, 1),
                observation_schedule=[],  # Invalid
                currency="USD", issuer_wallet="bank", holder_wallet="investor",
            )


# ============================================================================
# OBSERVATION TESTS - AUTOCALL
# ============================================================================

class TestComputeObservationAutocall:
    """Tests for compute_observation when autocall is triggered."""

    def _make_view(self, spot_perf=1.0, memory=0.0, obs_dates=None):
        """Helper to create a FakeView with autocallable state."""
        initial_spot = 100.0
        if obs_dates is None:
            obs_dates = [datetime(2024, 4, 15), datetime(2024, 7, 15)]
        return FakeView(
            balances={
                'bank': {'USD': Decimal("1000000")},
                'investor': {'AUTO': Decimal("1")},
            },
            states={
                'AUTO': {
                    'underlying': 'SPX',
                    'notional': Decimal("100000.0"),
                    'initial_spot': initial_spot,
                    'autocall_barrier': Decimal("1.0"),
                    'coupon_barrier': Decimal("0.7"),
                    'coupon_rate': Decimal("0.08"),
                    'put_barrier': Decimal("0.6"),
                    'issue_date': datetime(2024, 1, 15),
                    'maturity_date': datetime(2025, 1, 15),
                    'observation_schedule': obs_dates,
                    'currency': 'USD',
                    'issuer_wallet': 'bank',
                    'holder_wallet': 'investor',
                    'memory_feature': True,
                    'observation_history': [],
                    'coupon_memory': memory,
                    'put_knocked_in': False,
                    'autocalled': False,
                    'autocall_date': None,
                    'settled': False,
                }
            },
            time=datetime(2024, 4, 15)
        )

    def test_autocall_triggered_at_100_percent(self):
        """Autocall at exactly 100% of initial spot."""
        view = self._make_view()
        result = compute_observation(view, 'AUTO', datetime(2024, 4, 15), spot=100.0)

        assert not result.is_empty()
        assert len(result.moves) == 1

        move = result.moves[0]
        assert move.source == 'bank'
        assert move.dest == 'investor'
        assert move.unit_symbol == 'USD'
        # Principal + coupon = 100000 + 8000 = 108000
        assert move.quantity == Decimal("108000.0")

        sc = next(d for d in result.state_changes if d.unit == "AUTO")
        assert sc.new_state['autocalled'] is True
        assert sc.new_state['autocall_date'] == datetime(2024, 4, 15)
        assert sc.new_state['settled'] is True

    def test_autocall_triggered_above_barrier(self):
        """Autocall when spot > 100% of initial."""
        view = self._make_view()
        result = compute_observation(view, 'AUTO', datetime(2024, 4, 15), spot=110.0)

        assert not result.is_empty()
        move = result.moves[0]
        assert move.quantity == Decimal("108000.0")  # Same payout regardless of how far above

    def test_autocall_with_memory_coupon(self):
        """Autocall pays accumulated memory coupons."""
        view = self._make_view(memory=8000.0)  # One missed coupon
        result = compute_observation(view, 'AUTO', datetime(2024, 4, 15), spot=100.0)

        move = result.moves[0]
        # Principal + current coupon + memory = 100000 + 8000 + 8000 = 116000
        assert move.quantity == Decimal("116000.0")

    def test_autocall_clears_memory(self):
        """Autocall resets coupon memory to zero."""
        view = self._make_view(memory=16000.0)  # Two missed coupons
        result = compute_observation(view, 'AUTO', datetime(2024, 4, 15), spot=100.0)

        sc = next(d for d in result.state_changes if d.unit == "AUTO")
        assert sc.new_state['coupon_memory'] == 0.0


# ============================================================================
# OBSERVATION TESTS - COUPON
# ============================================================================

class TestComputeObservationCoupon:
    """Tests for compute_observation when coupon is paid."""

    def _make_view(self, memory=0.0, put_knocked=False):
        """Helper to create a FakeView with autocallable state."""
        return FakeView(
            balances={
                'bank': {'USD': Decimal("1000000")},
                'investor': {'AUTO': Decimal("1")},
            },
            states={
                'AUTO': {
                    'underlying': 'SPX',
                    'notional': Decimal("100000.0"),
                    'initial_spot': Decimal("100.0"),
                    'autocall_barrier': Decimal("1.0"),
                    'coupon_barrier': Decimal("0.7"),
                    'coupon_rate': Decimal("0.08"),
                    'put_barrier': Decimal("0.6"),
                    'issue_date': datetime(2024, 1, 15),
                    'maturity_date': datetime(2025, 1, 15),
                    'observation_schedule': [datetime(2024, 4, 15), datetime(2024, 7, 15)],
                    'currency': 'USD',
                    'issuer_wallet': 'bank',
                    'holder_wallet': 'investor',
                    'memory_feature': True,
                    'observation_history': [],
                    'coupon_memory': memory,
                    'put_knocked_in': put_knocked,
                    'autocalled': False,
                    'autocall_date': None,
                    'settled': False,
                }
            },
            time=datetime(2024, 4, 15)
        )

    def test_coupon_paid_above_barrier(self):
        """Coupon paid when spot >= 70% but < 100%."""
        view = self._make_view()
        # 80% of initial = above coupon barrier, below autocall
        result = compute_observation(view, 'AUTO', datetime(2024, 4, 15), spot=80.0)

        assert not result.is_empty()
        assert len(result.moves) == 1

        move = result.moves[0]
        assert move.source == 'bank'
        assert move.dest == 'investor'
        assert move.unit_symbol == 'USD'
        assert move.quantity == Decimal("8000.0")  # 8% of 100000

        sc = next(d for d in result.state_changes if d.unit == "AUTO")
        assert sc.new_state['autocalled'] is False
        assert sc.new_state['settled'] is False

    def test_coupon_at_exact_barrier(self):
        """Coupon paid when spot exactly at 70%."""
        view = self._make_view()
        result = compute_observation(view, 'AUTO', datetime(2024, 4, 15), spot=70.0)

        assert len(result.moves) == 1
        assert result.moves[0].quantity == 8000.0

    def test_coupon_with_memory_payout(self):
        """Coupon includes accumulated memory when paid."""
        view = self._make_view(memory=16000.0)  # Two missed coupons
        result = compute_observation(view, 'AUTO', datetime(2024, 4, 15), spot=80.0)

        move = result.moves[0]
        # Current coupon + memory = 8000 + 16000 = 24000
        assert move.quantity == Decimal("24000.0")

        sc = next(d for d in result.state_changes if d.unit == "AUTO")
        assert sc.new_state['coupon_memory'] == 0.0  # Memory cleared

    def test_observation_history_updated(self):
        """Observation history is properly recorded."""
        view = self._make_view()
        result = compute_observation(view, 'AUTO', datetime(2024, 4, 15), spot=80.0)

        sc = next(d for d in result.state_changes if d.unit == "AUTO")
        history = sc.new_state['observation_history']
        assert len(history) == 1
        obs = history[0]
        assert obs['date'] == datetime(2024, 4, 15)
        assert obs['spot'] == Decimal("80.0")
        assert obs['performance'] == Decimal("0.8")
        assert obs['autocalled'] is False
        assert obs['coupon_paid'] == Decimal("8000.0")


# ============================================================================
# OBSERVATION TESTS - MISSED COUPON
# ============================================================================

class TestComputeObservationMissedCoupon:
    """Tests for compute_observation when coupon is missed."""

    def _make_view(self, memory=0.0, memory_feature=True):
        """Helper to create a FakeView with autocallable state."""
        return FakeView(
            balances={
                'bank': {'USD': Decimal("1000000")},
                'investor': {'AUTO': Decimal("1")},
            },
            states={
                'AUTO': {
                    'underlying': 'SPX',
                    'notional': Decimal("100000.0"),
                    'initial_spot': Decimal("100.0"),
                    'autocall_barrier': Decimal("1.0"),
                    'coupon_barrier': Decimal("0.7"),
                    'coupon_rate': Decimal("0.08"),
                    'put_barrier': Decimal("0.6"),
                    'issue_date': datetime(2024, 1, 15),
                    'maturity_date': datetime(2025, 1, 15),
                    'observation_schedule': [
                        datetime(2024, 4, 15),
                        datetime(2024, 7, 15),
                        datetime(2024, 10, 15),
                    ],
                    'currency': 'USD',
                    'issuer_wallet': 'bank',
                    'holder_wallet': 'investor',
                    'memory_feature': memory_feature,
                    'observation_history': [],
                    'coupon_memory': memory,
                    'put_knocked_in': False,
                    'autocalled': False,
                    'autocall_date': None,
                    'settled': False,
                }
            },
            time=datetime(2024, 4, 15)
        )

    def test_coupon_missed_below_barrier(self):
        """No coupon when spot < 70%."""
        view = self._make_view()
        # 65% of initial = below coupon barrier
        result = compute_observation(view, 'AUTO', datetime(2024, 4, 15), spot=65.0)

        # No moves (no coupon paid)
        assert len(result.moves) == 0

        # But state is updated
        assert not result.is_empty()
        sc = next(d for d in result.state_changes if d.unit == "AUTO")
        assert sc.new_state['coupon_memory'] == 8000.0  # Coupon added to memory

    def test_memory_accumulates_over_periods(self):
        """Memory accumulates when multiple coupons are missed."""
        view = self._make_view(memory=8000.0)  # One already missed
        result = compute_observation(view, 'AUTO', datetime(2024, 4, 15), spot=65.0)

        sc = next(d for d in result.state_changes if d.unit == "AUTO")
        assert sc.new_state['coupon_memory'] == 16000.0  # Two missed coupons

    def test_no_memory_without_memory_feature(self):
        """Without memory feature, missed coupons are lost."""
        view = self._make_view(memory_feature=False)
        result = compute_observation(view, 'AUTO', datetime(2024, 4, 15), spot=65.0)

        sc = next(d for d in result.state_changes if d.unit == "AUTO")
        assert sc.new_state['coupon_memory'] == 0.0  # No memory accumulation


# ============================================================================
# OBSERVATION TESTS - PUT KNOCK-IN
# ============================================================================

class TestComputeObservationPutKnockIn:
    """Tests for compute_observation put barrier knock-in."""

    def _make_view(self, put_knocked=False):
        """Helper to create a FakeView with autocallable state."""
        return FakeView(
            balances={
                'bank': {'USD': Decimal("1000000")},
                'investor': {'AUTO': Decimal("1")},
            },
            states={
                'AUTO': {
                    'underlying': 'SPX',
                    'notional': Decimal("100000.0"),
                    'initial_spot': Decimal("100.0"),
                    'autocall_barrier': Decimal("1.0"),
                    'coupon_barrier': Decimal("0.7"),
                    'coupon_rate': Decimal("0.08"),
                    'put_barrier': Decimal("0.6"),
                    'issue_date': datetime(2024, 1, 15),
                    'maturity_date': datetime(2025, 1, 15),
                    'observation_schedule': [datetime(2024, 4, 15)],
                    'currency': 'USD',
                    'issuer_wallet': 'bank',
                    'holder_wallet': 'investor',
                    'memory_feature': True,
                    'observation_history': [],
                    'coupon_memory': Decimal("0.0"),
                    'put_knocked_in': put_knocked,
                    'autocalled': False,
                    'autocall_date': None,
                    'settled': False,
                }
            },
            time=datetime(2024, 4, 15)
        )

    def test_put_knocked_in_at_barrier(self):
        """Put knocks in at exactly 60% of initial."""
        view = self._make_view()
        result = compute_observation(view, 'AUTO', datetime(2024, 4, 15), spot=60.0)

        sc = next(d for d in result.state_changes if d.unit == "AUTO")
        assert sc.new_state['put_knocked_in'] is True

        history = sc.new_state['observation_history']
        assert history[0]['put_knocked_in'] is True

    def test_put_knocked_in_below_barrier(self):
        """Put knocks in below 60% of initial."""
        view = self._make_view()
        result = compute_observation(view, 'AUTO', datetime(2024, 4, 15), spot=50.0)

        sc = next(d for d in result.state_changes if d.unit == "AUTO")
        assert sc.new_state['put_knocked_in'] is True

    def test_put_not_knocked_above_barrier(self):
        """Put does not knock in above 60%."""
        view = self._make_view()
        result = compute_observation(view, 'AUTO', datetime(2024, 4, 15), spot=65.0)

        sc = next(d for d in result.state_changes if d.unit == "AUTO")
        assert sc.new_state['put_knocked_in'] is False

    def test_put_stays_knocked_in(self):
        """Once knocked in, put stays knocked in."""
        view = self._make_view(put_knocked=True)
        # Even if spot is above barrier now
        result = compute_observation(view, 'AUTO', datetime(2024, 4, 15), spot=80.0)

        sc = next(d for d in result.state_changes if d.unit == "AUTO")
        assert sc.new_state['put_knocked_in'] is True  # Still knocked in


# ============================================================================
# MATURITY PAYOFF TESTS
# ============================================================================

class TestComputeMaturityPayoff:
    """Tests for compute_maturity_payoff function."""

    def _make_view(self, put_knocked=False, memory=0.0, autocalled=False):
        """Helper to create a FakeView with autocallable state."""
        return FakeView(
            balances={
                'bank': {'USD': Decimal("1000000")},
                'investor': {'AUTO': Decimal("1")},
            },
            states={
                'AUTO': {
                    'underlying': 'SPX',
                    'notional': Decimal("100000.0"),
                    'initial_spot': Decimal("100.0"),
                    'autocall_barrier': Decimal("1.0"),
                    'coupon_barrier': Decimal("0.7"),
                    'coupon_rate': Decimal("0.08"),
                    'put_barrier': Decimal("0.6"),
                    'issue_date': datetime(2024, 1, 15),
                    'maturity_date': datetime(2025, 1, 15),
                    'observation_schedule': [datetime(2024, 4, 15)],
                    'currency': 'USD',
                    'issuer_wallet': 'bank',
                    'holder_wallet': 'investor',
                    'memory_feature': True,
                    'observation_history': [],
                    'coupon_memory': memory,
                    'put_knocked_in': put_knocked,
                    'autocalled': autocalled,
                    'autocall_date': None,
                    'settled': False,
                }
            },
            time=datetime(2025, 1, 15)
        )

    def test_maturity_without_knockin_full_principal(self):
        """Full principal returned if put not knocked in."""
        view = self._make_view(put_knocked=False)
        result = compute_maturity_payoff(view, 'AUTO', final_spot=90.0)

        assert len(result.moves) == 1
        move = result.moves[0]
        assert move.quantity == Decimal("100000.0")  # Full notional

        sc = next(d for d in result.state_changes if d.unit == "AUTO")
        assert sc.new_state['settled'] is True

    def test_maturity_with_knockin_reduced_payout(self):
        """Reduced payout if put knocked in and spot < initial."""
        view = self._make_view(put_knocked=True)
        # 50% of initial
        result = compute_maturity_payoff(view, 'AUTO', final_spot=50.0)

        move = result.moves[0]
        assert move.quantity == Decimal("50000.0")  # 50% of notional

    def test_maturity_with_knockin_capped_at_notional(self):
        """Payout capped at notional even if spot > initial."""
        view = self._make_view(put_knocked=True)
        # 120% of initial
        result = compute_maturity_payoff(view, 'AUTO', final_spot=120.0)

        move = result.moves[0]
        assert move.quantity == Decimal("100000.0")  # Capped at notional

    def test_maturity_with_memory_coupon(self):
        """Memory coupon added to maturity payout."""
        view = self._make_view(put_knocked=False, memory=16000.0)
        result = compute_maturity_payoff(view, 'AUTO', final_spot=90.0)

        move = result.moves[0]
        # Notional + memory = 100000 + 16000 = 116000
        assert move.quantity == Decimal("116000.0")

    def test_maturity_with_knockin_and_memory(self):
        """Knock-in loss + memory coupon."""
        view = self._make_view(put_knocked=True, memory=8000.0)
        # 60% of initial
        result = compute_maturity_payoff(view, 'AUTO', final_spot=60.0)

        move = result.moves[0]
        # 60% of notional + memory = 60000 + 8000 = 68000
        assert move.quantity == Decimal("68000.0")

    def test_maturity_already_autocalled(self):
        """No action if already autocalled."""
        view = self._make_view(autocalled=True)
        result = compute_maturity_payoff(view, 'AUTO', final_spot=100.0)

        assert result.is_empty()

    def test_maturity_invalid_spot_raises(self):
        """Non-positive spot raises ValueError."""
        view = self._make_view()
        with pytest.raises(ValueError, match="final_spot must be positive"):
            compute_maturity_payoff(view, 'AUTO', final_spot=0.0)


# ============================================================================
# EDGE CASES
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def _make_view(self):
        """Helper to create a FakeView with autocallable state."""
        return FakeView(
            balances={
                'bank': {'USD': Decimal("1000000")},
                'investor': {'AUTO': Decimal("1")},
            },
            states={
                'AUTO': {
                    'underlying': 'SPX',
                    'notional': Decimal("100000.0"),
                    'initial_spot': Decimal("100.0"),
                    'autocall_barrier': Decimal("1.0"),
                    'coupon_barrier': Decimal("0.7"),
                    'coupon_rate': Decimal("0.08"),
                    'put_barrier': Decimal("0.6"),
                    'issue_date': datetime(2024, 1, 15),
                    'maturity_date': datetime(2025, 1, 15),
                    'observation_schedule': [datetime(2024, 4, 15), datetime(2024, 7, 15)],
                    'currency': 'USD',
                    'issuer_wallet': 'bank',
                    'holder_wallet': 'investor',
                    'memory_feature': True,
                    'observation_history': [],
                    'coupon_memory': Decimal("0.0"),
                    'put_knocked_in': False,
                    'autocalled': False,
                    'autocall_date': None,
                    'settled': False,
                }
            },
            time=datetime(2024, 4, 15)
        )

    def test_observation_not_in_schedule(self):
        """Observation on non-scheduled date returns empty."""
        view = self._make_view()
        result = compute_observation(view, 'AUTO', datetime(2024, 5, 15), spot=100.0)
        assert result.is_empty()

    def test_observation_already_processed(self):
        """Already processed observation returns empty."""
        view = FakeView(
            balances={'bank': {'USD': Decimal("1000000")}, 'investor': {'AUTO': Decimal("1")}},
            states={
                'AUTO': {
                    'underlying': 'SPX',
                    'notional': Decimal("100000.0"),
                    'initial_spot': Decimal("100.0"),
                    'autocall_barrier': Decimal("1.0"),
                    'coupon_barrier': Decimal("0.7"),
                    'coupon_rate': Decimal("0.08"),
                    'put_barrier': Decimal("0.6"),
                    'issue_date': datetime(2024, 1, 15),
                    'maturity_date': datetime(2025, 1, 15),
                    'observation_schedule': [datetime(2024, 4, 15)],
                    'currency': 'USD',
                    'issuer_wallet': 'bank',
                    'holder_wallet': 'investor',
                    'memory_feature': True,
                    'observation_history': [
                        {'date': datetime(2024, 4, 15), 'spot': Decimal("80.0"), 'performance': Decimal("0.8"),
                         'autocalled': False, 'coupon_paid': Decimal("8000.0"), 'memory_paid': Decimal("0.0"),
                         'put_knocked_in': False}
                    ],
                    'coupon_memory': 0.0,
                    'put_knocked_in': False,
                    'autocalled': False,
                    'autocall_date': None,
                    'settled': False,
                }
            },
            time=datetime(2024, 4, 15)
        )
        result = compute_observation(view, 'AUTO', datetime(2024, 4, 15), spot=100.0)
        assert result.is_empty()

    def test_observation_already_autocalled(self):
        """Observation after autocall returns empty."""
        view = FakeView(
            balances={'bank': {'USD': Decimal("1000000")}, 'investor': {'AUTO': Decimal("1")}},
            states={
                'AUTO': {
                    'underlying': 'SPX',
                    'notional': Decimal("100000.0"),
                    'initial_spot': Decimal("100.0"),
                    'autocall_barrier': Decimal("1.0"),
                    'coupon_barrier': Decimal("0.7"),
                    'coupon_rate': Decimal("0.08"),
                    'put_barrier': Decimal("0.6"),
                    'issue_date': datetime(2024, 1, 15),
                    'maturity_date': datetime(2025, 1, 15),
                    'observation_schedule': [datetime(2024, 4, 15), datetime(2024, 7, 15)],
                    'currency': 'USD',
                    'issuer_wallet': 'bank',
                    'holder_wallet': 'investor',
                    'memory_feature': True,
                    'observation_history': [],
                    'coupon_memory': Decimal("0.0"),
                    'put_knocked_in': False,
                    'autocalled': True,
                    'autocall_date': datetime(2024, 4, 15),
                    'settled': True,
                }
            },
            time=datetime(2024, 7, 15)
        )
        result = compute_observation(view, 'AUTO', datetime(2024, 7, 15), spot=100.0)
        assert result.is_empty()

    def test_observation_invalid_spot_raises(self):
        """Non-positive spot raises ValueError."""
        view = self._make_view()
        with pytest.raises(ValueError, match="spot must be positive"):
            compute_observation(view, 'AUTO', datetime(2024, 4, 15), spot=-10.0)

    def test_spot_exactly_between_barriers(self):
        """Spot exactly at coupon barrier but below autocall."""
        view = self._make_view()
        # At 70% = coupon barrier, below 100% = autocall barrier
        result = compute_observation(view, 'AUTO', datetime(2024, 4, 15), spot=70.0)

        # Should pay coupon but not autocall
        assert len(result.moves) == 1
        assert result.moves[0].quantity == 8000.0
        sc = next(d for d in result.state_changes if d.unit == "AUTO")
        assert sc.new_state['autocalled'] is False


# ============================================================================
# TRANSACT INTERFACE TESTS
# ============================================================================

class TestTransact:
    """Tests for transact() event routing function."""

    def _make_view(self):
        """Helper to create a FakeView with autocallable state."""
        return FakeView(
            balances={
                'bank': {'USD': Decimal("1000000")},
                'investor': {'AUTO': Decimal("1")},
            },
            states={
                'AUTO': {
                    'underlying': 'SPX',
                    'notional': Decimal("100000.0"),
                    'initial_spot': Decimal("100.0"),
                    'autocall_barrier': Decimal("1.0"),
                    'coupon_barrier': Decimal("0.7"),
                    'coupon_rate': Decimal("0.08"),
                    'put_barrier': Decimal("0.6"),
                    'issue_date': datetime(2024, 1, 15),
                    'maturity_date': datetime(2025, 1, 15),
                    'observation_schedule': [datetime(2024, 4, 15)],
                    'currency': 'USD',
                    'issuer_wallet': 'bank',
                    'holder_wallet': 'investor',
                    'memory_feature': True,
                    'observation_history': [],
                    'coupon_memory': Decimal("0.0"),
                    'put_knocked_in': False,
                    'autocalled': False,
                    'autocall_date': None,
                    'settled': False,
                }
            },
            time=datetime(2024, 4, 15)
        )

    def test_lifecycle_event_observation(self):
        """_process_lifecycle_event OBSERVATION event routes correctly."""
        view = self._make_view()
        result = autocallable_lifecycle_event(
            view, 'AUTO', 'OBSERVATION',
            datetime(2024, 4, 15),
            spot=80.0
        )

        assert len(result.moves) == 1
        assert result.moves[0].quantity == 8000.0

    def test_lifecycle_event_maturity(self):
        """_process_lifecycle_event MATURITY event routes correctly."""
        view = self._make_view()
        result = autocallable_lifecycle_event(
            view, 'AUTO', 'MATURITY',
            datetime(2025, 1, 15),
            final_spot=90.0
        )

        assert len(result.moves) == 1
        assert result.moves[0].quantity == 100000.0

    def test_lifecycle_event_missing_spot(self):
        """_process_lifecycle_event OBSERVATION without spot returns empty."""
        view = self._make_view()
        result = autocallable_lifecycle_event(
            view, 'AUTO', 'OBSERVATION',
            datetime(2024, 4, 15)
            # spot missing
        )
        assert result.is_empty()

    def test_lifecycle_event_missing_final_spot(self):
        """_process_lifecycle_event MATURITY without final_spot returns empty."""
        view = self._make_view()
        result = autocallable_lifecycle_event(
            view, 'AUTO', 'MATURITY',
            datetime(2025, 1, 15)
            # final_spot missing
        )
        assert result.is_empty()

    def test_lifecycle_event_unknown(self):
        """_process_lifecycle_event with unknown event type returns empty."""
        view = self._make_view()
        result = autocallable_lifecycle_event(
            view, 'AUTO', 'UNKNOWN_EVENT',
            datetime(2024, 4, 15),
            spot=80.0
        )
        assert result.is_empty()


# ============================================================================
# SMART CONTRACT TESTS
# ============================================================================

class TestAutocallableContract:
    """Tests for autocallable_contract SmartContract function."""

    def _make_view(self, obs_dates=None, history=None, autocalled=False, settled=False):
        """Helper to create a FakeView with autocallable state."""
        if obs_dates is None:
            obs_dates = [datetime(2024, 4, 15), datetime(2024, 7, 15)]
        if history is None:
            history = []
        return FakeView(
            balances={
                'bank': {'USD': Decimal("1000000")},
                'investor': {'AUTO': Decimal("1")},
            },
            states={
                'AUTO': {
                    'underlying': 'SPX',
                    'notional': Decimal("100000.0"),
                    'initial_spot': Decimal("100.0"),
                    'autocall_barrier': Decimal("1.0"),
                    'coupon_barrier': Decimal("0.7"),
                    'coupon_rate': Decimal("0.08"),
                    'put_barrier': Decimal("0.6"),
                    'issue_date': datetime(2024, 1, 15),
                    'maturity_date': datetime(2025, 1, 15),
                    'observation_schedule': obs_dates,
                    'currency': 'USD',
                    'issuer_wallet': 'bank',
                    'holder_wallet': 'investor',
                    'memory_feature': True,
                    'observation_history': history,
                    'coupon_memory': Decimal("0.0"),
                    'put_knocked_in': False,
                    'autocalled': autocalled,
                    'autocall_date': None,
                    'settled': settled,
                }
            },
            time=datetime(2024, 4, 15)
        )

    def test_contract_processes_observation(self):
        """Contract processes due observation."""
        view = self._make_view()
        result = autocallable_contract(
            view, 'AUTO',
            datetime(2024, 4, 15),
            {'SPX': Decimal("80.0")}
        )

        assert len(result.moves) == 1
        assert result.moves[0].quantity == 8000.0

    def test_contract_processes_maturity(self):
        """Contract processes maturity."""
        view = self._make_view(
            obs_dates=[datetime(2024, 4, 15)],
            history=[{'date': datetime(2024, 4, 15), 'spot': Decimal("80.0"), 'performance': Decimal("0.8"),
                      'autocalled': False, 'coupon_paid': Decimal("8000.0"), 'memory_paid': Decimal("0.0"),
                      'put_knocked_in': False}]
        )
        result = autocallable_contract(
            view, 'AUTO',
            datetime(2025, 1, 15),
            {'SPX': Decimal("90.0")}
        )

        assert len(result.moves) == 1
        assert result.moves[0].quantity == 100000.0

    def test_contract_already_settled_empty(self):
        """Contract returns empty if already settled."""
        view = self._make_view(settled=True)
        result = autocallable_contract(
            view, 'AUTO',
            datetime(2024, 4, 15),
            {'SPX': Decimal("100.0")}
        )
        assert result.is_empty()

    def test_contract_missing_price_raises(self):
        """Contract raises ValueError if underlying price missing."""
        view = self._make_view()
        with pytest.raises(ValueError, match="Missing price for autocallable underlying"):
            autocallable_contract(
                view, 'AUTO',
                datetime(2024, 4, 15),
                {'AAPL': Decimal("150.0")}  # Wrong underlying
            )


# ============================================================================
# HELPER FUNCTION TESTS
# ============================================================================

class TestHelperFunctions:
    """Tests for helper functions."""

    def _make_view(self, history=None, memory=0.0, autocalled=False, put_knocked=False):
        """Helper to create a FakeView with autocallable state."""
        if history is None:
            history = []
        return FakeView(
            balances={
                'bank': {'USD': Decimal("1000000")},
                'investor': {'AUTO': Decimal("1")},
            },
            states={
                'AUTO': {
                    'underlying': 'SPX',
                    'notional': Decimal("100000.0"),
                    'initial_spot': Decimal("100.0"),
                    'autocall_barrier': Decimal("1.0"),
                    'coupon_barrier': Decimal("0.7"),
                    'coupon_rate': Decimal("0.08"),
                    'put_barrier': Decimal("0.6"),
                    'issue_date': datetime(2024, 1, 15),
                    'maturity_date': datetime(2025, 1, 15),
                    'observation_schedule': [
                        datetime(2024, 4, 15),
                        datetime(2024, 7, 15),
                        datetime(2024, 10, 15),
                    ],
                    'currency': 'USD',
                    'issuer_wallet': 'bank',
                    'holder_wallet': 'investor',
                    'memory_feature': True,
                    'observation_history': history,
                    'coupon_memory': memory,
                    'put_knocked_in': put_knocked,
                    'autocalled': autocalled,
                    'autocall_date': datetime(2024, 4, 15) if autocalled else None,
                    'settled': False,
                }
            },
            time=datetime(2024, 4, 15)
        )

    def test_get_status_initial(self):
        """Get status of fresh autocallable."""
        view = self._make_view()
        status = get_autocallable_status(view, 'AUTO')

        assert status['autocalled'] is False
        assert status['autocall_date'] is None
        assert status['settled'] is False
        assert status['put_knocked_in'] is False
        assert status['coupon_memory'] == 0.0
        assert status['observations_processed'] == 0
        assert status['total_observations'] == 3
        assert status['next_observation'] == datetime(2024, 4, 15)

    def test_get_status_after_observation(self):
        """Get status after observation processed."""
        history = [
            {'date': datetime(2024, 4, 15), 'spot': Decimal("80.0"), 'performance': Decimal("0.8"),
             'autocalled': False, 'coupon_paid': Decimal("8000.0"), 'memory_paid': Decimal("0.0"),
             'put_knocked_in': False}
        ]
        view = self._make_view(history=history)
        status = get_autocallable_status(view, 'AUTO')

        assert status['observations_processed'] == 1
        assert status['next_observation'] == datetime(2024, 7, 15)

    def test_get_status_autocalled(self):
        """Get status when autocalled."""
        view = self._make_view(autocalled=True)
        status = get_autocallable_status(view, 'AUTO')

        assert status['autocalled'] is True
        assert status['autocall_date'] == datetime(2024, 4, 15)

    def test_get_total_coupons_paid(self):
        """Get total coupons paid."""
        history = [
            {'date': datetime(2024, 4, 15), 'spot': Decimal("80.0"), 'performance': Decimal("0.8"),
             'autocalled': False, 'coupon_paid': Decimal("8000.0"), 'memory_paid': Decimal("0.0"),
             'put_knocked_in': False},
            {'date': datetime(2024, 7, 15), 'spot': Decimal("75.0"), 'performance': Decimal("0.75"),
             'autocalled': False, 'coupon_paid': Decimal("8000.0"), 'memory_paid': Decimal("0.0"),
             'put_knocked_in': False},
        ]
        view = self._make_view(history=history)
        total = get_total_coupons_paid(view, 'AUTO')

        assert total == Decimal("16000.0")

    def test_get_total_coupons_with_memory(self):
        """Get total coupons including memory payouts."""
        history = [
            {'date': datetime(2024, 4, 15), 'spot': Decimal("60.0"), 'performance': Decimal("0.6"),
             'autocalled': False, 'coupon_paid': Decimal("0.0"), 'memory_paid': Decimal("0.0"),
             'put_knocked_in': True},  # Missed
            {'date': datetime(2024, 7, 15), 'spot': Decimal("80.0"), 'performance': Decimal("0.8"),
             'autocalled': False, 'coupon_paid': Decimal("8000.0"), 'memory_paid': Decimal("8000.0"),
             'put_knocked_in': False},  # Paid with memory
        ]
        view = self._make_view(history=history)
        total = get_total_coupons_paid(view, 'AUTO')

        assert total == Decimal("16000.0")  # 8000 coupon + 8000 memory


# ============================================================================
# FULL LIFECYCLE TESTS
# ============================================================================

class TestFullLifecycle:
    """Tests for complete autocallable lifecycle scenarios."""

    def test_lifecycle_autocall_first_observation(self):
        """Autocall on first observation."""
        view = FakeView(
            balances={'bank': {'USD': Decimal("1000000")}, 'investor': {'AUTO': Decimal("1")}},
            states={
                'AUTO': {
                    'underlying': 'SPX',
                    'notional': Decimal("100000.0"),
                    'initial_spot': Decimal("100.0"),
                    'autocall_barrier': Decimal("1.0"),
                    'coupon_barrier': Decimal("0.7"),
                    'coupon_rate': Decimal("0.08"),
                    'put_barrier': Decimal("0.6"),
                    'issue_date': datetime(2024, 1, 15),
                    'maturity_date': datetime(2025, 1, 15),
                    'observation_schedule': [
                        datetime(2024, 4, 15),
                        datetime(2024, 7, 15),
                        datetime(2024, 10, 15),
                        datetime(2025, 1, 15),
                    ],
                    'currency': 'USD',
                    'issuer_wallet': 'bank',
                    'holder_wallet': 'investor',
                    'memory_feature': True,
                    'observation_history': [],
                    'coupon_memory': Decimal("0.0"),
                    'put_knocked_in': False,
                    'autocalled': False,
                    'autocall_date': None,
                    'settled': False,
                }
            },
            time=datetime(2024, 4, 15)
        )

        result = compute_observation(view, 'AUTO', datetime(2024, 4, 15), spot=100.0)

        sc = next(d for d in result.state_changes if d.unit == "AUTO")
        assert sc.new_state['autocalled'] is True
        assert result.moves[0].quantity == 108000.0

    def test_lifecycle_coupons_then_maturity(self):
        """Multiple coupon payments then maturity."""
        # First observation - coupon paid
        view1 = FakeView(
            balances={'bank': {'USD': Decimal("1000000")}, 'investor': {'AUTO': Decimal("1")}},
            states={
                'AUTO': {
                    'underlying': 'SPX',
                    'notional': Decimal("100000.0"),
                    'initial_spot': Decimal("100.0"),
                    'autocall_barrier': Decimal("1.0"),
                    'coupon_barrier': Decimal("0.7"),
                    'coupon_rate': Decimal("0.08"),
                    'put_barrier': Decimal("0.6"),
                    'issue_date': datetime(2024, 1, 15),
                    'maturity_date': datetime(2025, 1, 15),
                    'observation_schedule': [
                        datetime(2024, 4, 15),
                        datetime(2024, 7, 15),
                    ],
                    'currency': 'USD',
                    'issuer_wallet': 'bank',
                    'holder_wallet': 'investor',
                    'memory_feature': True,
                    'observation_history': [],
                    'coupon_memory': Decimal("0.0"),
                    'put_knocked_in': False,
                    'autocalled': False,
                    'autocall_date': None,
                    'settled': False,
                }
            },
            time=datetime(2024, 4, 15)
        )

        result1 = compute_observation(view1, 'AUTO', datetime(2024, 4, 15), spot=80.0)
        assert result1.moves[0].quantity == 8000.0

        # Second observation - coupon paid
        view2 = FakeView(
            balances={'bank': {'USD': Decimal("1000000")}, 'investor': {'AUTO': Decimal("1")}},
            states={
                'AUTO': {
                    **(next(d for d in result1.state_changes if d.unit == 'AUTO').new_state),
                }
            },
            time=datetime(2024, 7, 15)
        )

        result2 = compute_observation(view2, 'AUTO', datetime(2024, 7, 15), spot=75.0)
        assert result2.moves[0].quantity == 8000.0

        # Maturity
        view3 = FakeView(
            balances={'bank': {'USD': Decimal("1000000")}, 'investor': {'AUTO': Decimal("1")}},
            states={
                'AUTO': {
                    **(next(d for d in result2.state_changes if d.unit == 'AUTO').new_state),
                }
            },
            time=datetime(2025, 1, 15)
        )

        result3 = compute_maturity_payoff(view3, 'AUTO', final_spot=90.0)
        assert result3.moves[0].quantity == 100000.0

    def test_lifecycle_memory_accumulation_then_payout(self):
        """Miss coupons, accumulate memory, then pay all."""
        # First observation - missed (below coupon barrier)
        view1 = FakeView(
            balances={'bank': {'USD': Decimal("1000000")}, 'investor': {'AUTO': Decimal("1")}},
            states={
                'AUTO': {
                    'underlying': 'SPX',
                    'notional': Decimal("100000.0"),
                    'initial_spot': Decimal("100.0"),
                    'autocall_barrier': Decimal("1.0"),
                    'coupon_barrier': Decimal("0.7"),
                    'coupon_rate': Decimal("0.08"),
                    'put_barrier': Decimal("0.6"),
                    'issue_date': datetime(2024, 1, 15),
                    'maturity_date': datetime(2025, 1, 15),
                    'observation_schedule': [
                        datetime(2024, 4, 15),
                        datetime(2024, 7, 15),
                        datetime(2024, 10, 15),
                    ],
                    'currency': 'USD',
                    'issuer_wallet': 'bank',
                    'holder_wallet': 'investor',
                    'memory_feature': True,
                    'observation_history': [],
                    'coupon_memory': Decimal("0.0"),
                    'put_knocked_in': False,
                    'autocalled': False,
                    'autocall_date': None,
                    'settled': False,
                }
            },
            time=datetime(2024, 4, 15)
        )

        result1 = compute_observation(view1, 'AUTO', datetime(2024, 4, 15), spot=65.0)
        assert len(result1.moves) == 0  # No coupon
        assert next(d for d in result1.state_changes if d.unit == 'AUTO').new_state['coupon_memory'] == 8000.0

        # Second observation - also missed
        view2 = FakeView(
            balances={'bank': {'USD': Decimal("1000000")}, 'investor': {'AUTO': Decimal("1")}},
            states={'AUTO': next(d for d in result1.state_changes if d.unit == 'AUTO').new_state},
            time=datetime(2024, 7, 15)
        )

        result2 = compute_observation(view2, 'AUTO', datetime(2024, 7, 15), spot=60.0)
        assert len(result2.moves) == 0
        assert next(d for d in result2.state_changes if d.unit == 'AUTO').new_state['coupon_memory'] == 16000.0

        # Third observation - above coupon barrier, pay all memory
        view3 = FakeView(
            balances={'bank': {'USD': Decimal("1000000")}, 'investor': {'AUTO': Decimal("1")}},
            states={'AUTO': next(d for d in result2.state_changes if d.unit == 'AUTO').new_state},
            time=datetime(2024, 10, 15)
        )

        result3 = compute_observation(view3, 'AUTO', datetime(2024, 10, 15), spot=80.0)
        # Current coupon + 2 missed = 8000 + 16000 = 24000
        assert result3.moves[0].quantity == 24000.0
        assert next(d for d in result3.state_changes if d.unit == 'AUTO').new_state['coupon_memory'] == 0.0

    def test_lifecycle_knockin_then_loss(self):
        """Put knocks in, then loss at maturity."""
        # First observation - knock in (spot at 55%, below coupon barrier too)
        view1 = FakeView(
            balances={'bank': {'USD': Decimal("1000000")}, 'investor': {'AUTO': Decimal("1")}},
            states={
                'AUTO': {
                    'underlying': 'SPX',
                    'notional': Decimal("100000.0"),
                    'initial_spot': Decimal("100.0"),
                    'autocall_barrier': Decimal("1.0"),
                    'coupon_barrier': Decimal("0.7"),
                    'coupon_rate': Decimal("0.08"),
                    'put_barrier': Decimal("0.6"),
                    'issue_date': datetime(2024, 1, 15),
                    'maturity_date': datetime(2025, 1, 15),
                    'observation_schedule': [datetime(2024, 4, 15)],
                    'currency': 'USD',
                    'issuer_wallet': 'bank',
                    'holder_wallet': 'investor',
                    'memory_feature': True,
                    'observation_history': [],
                    'coupon_memory': Decimal("0.0"),
                    'put_knocked_in': False,
                    'autocalled': False,
                    'autocall_date': None,
                    'settled': False,
                }
            },
            time=datetime(2024, 4, 15)
        )

        result1 = compute_observation(view1, 'AUTO', datetime(2024, 4, 15), spot=55.0)
        assert next(d for d in result1.state_changes if d.unit == 'AUTO').new_state['put_knocked_in'] is True
        # Coupon was missed (55% < 70% coupon barrier), so memory = 8000
        assert next(d for d in result1.state_changes if d.unit == 'AUTO').new_state['coupon_memory'] == 8000.0

        # Maturity with loss
        view2 = FakeView(
            balances={'bank': {'USD': Decimal("1000000")}, 'investor': {'AUTO': Decimal("1")}},
            states={'AUTO': next(d for d in result1.state_changes if d.unit == 'AUTO').new_state},
            time=datetime(2025, 1, 15)
        )

        result2 = compute_maturity_payoff(view2, 'AUTO', final_spot=70.0)
        # 70% of notional + memory coupon = 70000 + 8000 = 78000
        assert result2.moves[0].quantity == 78000.0


# ============================================================================
# CONSERVATION LAW TESTS
# ============================================================================

class TestPositionTransfer:
    """Tests for payments to current position holders (not original holder_wallet)."""

    def test_coupon_payment_to_current_holder_after_transfer(self):
        """Coupon payment goes to current holder, not original holder_wallet."""
        # Create autocallable with alice as original holder
        view = FakeView(
            balances={
                'bank': {'USD': Decimal("1000000")},
                'alice': {},  # alice no longer holds the autocallable
                'bob': {'AUTO': Decimal("1")},  # bob now holds it (transferred from alice)
            },
            states={
                'AUTO': {
                    'underlying': 'SPX',
                    'notional': Decimal("100000.0"),
                    'initial_spot': Decimal("100.0"),
                    'autocall_barrier': Decimal("1.0"),
                    'coupon_barrier': Decimal("0.7"),
                    'coupon_rate': Decimal("0.08"),
                    'put_barrier': Decimal("0.6"),
                    'issue_date': datetime(2024, 1, 15),
                    'maturity_date': datetime(2025, 1, 15),
                    'observation_schedule': [datetime(2024, 4, 15)],
                    'currency': 'USD',
                    'issuer_wallet': 'bank',
                    'holder_wallet': 'alice',  # Original holder in state
                    'memory_feature': True,
                    'observation_history': [],
                    'coupon_memory': Decimal("0.0"),
                    'put_knocked_in': False,
                    'autocalled': False,
                    'autocall_date': None,
                    'settled': False,
                }
            },
            time=datetime(2024, 4, 15)
        )

        # Trigger coupon payment (spot at 80% - above coupon barrier)
        result = compute_observation(view, 'AUTO', datetime(2024, 4, 15), spot=80.0)

        # Payment should go to bob (current holder), not alice (original holder_wallet)
        assert len(result.moves) == 1
        move = result.moves[0]
        assert move.source == 'bank'
        assert move.dest == 'bob'  # Current holder gets payment
        assert move.unit_symbol == 'USD'
        assert move.quantity == Decimal("8000.0")  # 8% of 100000

    def test_autocall_redemption_to_current_holder_after_transfer(self):
        """Autocall redemption goes to current holder, not original holder_wallet."""
        # Create autocallable with alice as original holder, bob as current holder
        view = FakeView(
            balances={
                'bank': {'USD': Decimal("1000000")},
                'alice': {},
                'bob': {'AUTO': Decimal("1")},  # bob holds it now
            },
            states={
                'AUTO': {
                    'underlying': 'SPX',
                    'notional': Decimal("100000.0"),
                    'initial_spot': Decimal("100.0"),
                    'autocall_barrier': Decimal("1.0"),
                    'coupon_barrier': Decimal("0.7"),
                    'coupon_rate': Decimal("0.08"),
                    'put_barrier': Decimal("0.6"),
                    'issue_date': datetime(2024, 1, 15),
                    'maturity_date': datetime(2025, 1, 15),
                    'observation_schedule': [datetime(2024, 4, 15)],
                    'currency': 'USD',
                    'issuer_wallet': 'bank',
                    'holder_wallet': 'alice',  # Original holder
                    'memory_feature': True,
                    'observation_history': [],
                    'coupon_memory': Decimal("0.0"),
                    'put_knocked_in': False,
                    'autocalled': False,
                    'autocall_date': None,
                    'settled': False,
                }
            },
            time=datetime(2024, 4, 15)
        )

        # Trigger autocall (spot at 100% - autocall barrier)
        result = compute_observation(view, 'AUTO', datetime(2024, 4, 15), spot=100.0)

        # Autocall redemption should go to bob, not alice
        assert len(result.moves) == 1
        move = result.moves[0]
        assert move.source == 'bank'
        assert move.dest == 'bob'  # Current holder
        assert move.unit_symbol == 'USD'
        assert move.quantity == Decimal("108000.0")  # 100000 principal + 8000 coupon

    def test_maturity_payoff_to_current_holder_after_transfer(self):
        """Maturity payoff goes to current holder, not original holder_wallet."""
        # Create autocallable with alice as original holder, bob as current holder
        view = FakeView(
            balances={
                'bank': {'USD': Decimal("1000000")},
                'alice': {},
                'bob': {'AUTO': Decimal("1")},  # bob holds it now
            },
            states={
                'AUTO': {
                    'underlying': 'SPX',
                    'notional': Decimal("100000.0"),
                    'initial_spot': Decimal("100.0"),
                    'autocall_barrier': Decimal("1.0"),
                    'coupon_barrier': Decimal("0.7"),
                    'coupon_rate': Decimal("0.08"),
                    'put_barrier': Decimal("0.6"),
                    'issue_date': datetime(2024, 1, 15),
                    'maturity_date': datetime(2025, 1, 15),
                    'observation_schedule': [datetime(2024, 4, 15)],
                    'currency': 'USD',
                    'issuer_wallet': 'bank',
                    'holder_wallet': 'alice',  # Original holder
                    'memory_feature': True,
                    'observation_history': [],
                    'coupon_memory': Decimal("0.0"),
                    'put_knocked_in': False,
                    'autocalled': False,
                    'autocall_date': None,
                    'settled': False,
                }
            },
            time=datetime(2025, 1, 15)
        )

        # Trigger maturity payment
        result = compute_maturity_payoff(view, 'AUTO', final_spot=90.0)

        # Maturity payment should go to bob, not alice
        assert len(result.moves) == 1
        move = result.moves[0]
        assert move.source == 'bank'
        assert move.dest == 'bob'  # Current holder
        assert move.unit_symbol == 'USD'
        assert move.quantity == Decimal("100000.0")  # Full principal (no knock-in)

    def test_multiple_holders_share_coupon_payment(self):
        """Multiple holders each receive proportional coupon payments."""
        # Create autocallable with alice and bob each holding 0.5 units
        view = FakeView(
            balances={
                'bank': {'USD': Decimal("1000000")},
                'alice': {'AUTO': Decimal("0.5")},
                'bob': {'AUTO': Decimal("0.5")},
            },
            states={
                'AUTO': {
                    'underlying': 'SPX',
                    'notional': Decimal("100000.0"),
                    'initial_spot': Decimal("100.0"),
                    'autocall_barrier': Decimal("1.0"),
                    'coupon_barrier': Decimal("0.7"),
                    'coupon_rate': Decimal("0.08"),
                    'put_barrier': Decimal("0.6"),
                    'issue_date': datetime(2024, 1, 15),
                    'maturity_date': datetime(2025, 1, 15),
                    'observation_schedule': [datetime(2024, 4, 15)],
                    'currency': 'USD',
                    'issuer_wallet': 'bank',
                    'holder_wallet': 'alice',  # Original holder
                    'memory_feature': True,
                    'observation_history': [],
                    'coupon_memory': Decimal("0.0"),
                    'put_knocked_in': False,
                    'autocalled': False,
                    'autocall_date': None,
                    'settled': False,
                }
            },
            time=datetime(2024, 4, 15)
        )

        # Trigger coupon payment
        result = compute_observation(view, 'AUTO', datetime(2024, 4, 15), spot=80.0)

        # Both alice and bob should receive proportional payments
        assert len(result.moves) == 2

        # Moves should be sorted by wallet name (alice, bob)
        alice_move = result.moves[0]
        assert alice_move.source == 'bank'
        assert alice_move.dest == 'alice'
        assert alice_move.unit_symbol == 'USD'
        assert alice_move.quantity == Decimal("4000.0")  # 0.5 * 8000

        bob_move = result.moves[1]
        assert bob_move.source == 'bank'
        assert bob_move.dest == 'bob'
        assert bob_move.unit_symbol == 'USD'
        assert bob_move.quantity == Decimal("4000.0")  # 0.5 * 8000

    def test_issuer_holding_units_does_not_receive_payment(self):
        """Issuer holding autocallable units should not receive payment."""
        view = FakeView(
            balances={
                'bank': {'USD': Decimal("1000000"), 'AUTO': Decimal("0.3")},  # bank holds some units
                'alice': {'AUTO': Decimal("0.7")},
            },
            states={
                'AUTO': {
                    'underlying': 'SPX',
                    'notional': Decimal("100000.0"),
                    'initial_spot': Decimal("100.0"),
                    'autocall_barrier': Decimal("1.0"),
                    'coupon_barrier': Decimal("0.7"),
                    'coupon_rate': Decimal("0.08"),
                    'put_barrier': Decimal("0.6"),
                    'issue_date': datetime(2024, 1, 15),
                    'maturity_date': datetime(2025, 1, 15),
                    'observation_schedule': [datetime(2024, 4, 15)],
                    'currency': 'USD',
                    'issuer_wallet': 'bank',
                    'holder_wallet': 'alice',
                    'memory_feature': True,
                    'observation_history': [],
                    'coupon_memory': Decimal("0.0"),
                    'put_knocked_in': False,
                    'autocalled': False,
                    'autocall_date': None,
                    'settled': False,
                }
            },
            time=datetime(2024, 4, 15)
        )

        # Trigger coupon payment
        result = compute_observation(view, 'AUTO', datetime(2024, 4, 15), spot=80.0)

        # Only alice should receive payment (bank is excluded as issuer)
        assert len(result.moves) == 1
        move = result.moves[0]
        assert move.dest == 'alice'
        assert move.quantity == Decimal("5600.0")  # 0.7 * 8000


class TestConservationLaws:
    """Tests for financial conservation laws."""

    def test_coupon_payment_conservation(self):
        """Coupon moves from issuer to holder."""
        view = FakeView(
            balances={'bank': {'USD': Decimal("1000000")}, 'investor': {'AUTO': Decimal("1")}},
            states={
                'AUTO': {
                    'underlying': 'SPX',
                    'notional': Decimal("100000.0"),
                    'initial_spot': Decimal("100.0"),
                    'autocall_barrier': Decimal("1.0"),
                    'coupon_barrier': Decimal("0.7"),
                    'coupon_rate': Decimal("0.08"),
                    'put_barrier': Decimal("0.6"),
                    'issue_date': datetime(2024, 1, 15),
                    'maturity_date': datetime(2025, 1, 15),
                    'observation_schedule': [datetime(2024, 4, 15)],
                    'currency': 'USD',
                    'issuer_wallet': 'bank',
                    'holder_wallet': 'investor',
                    'memory_feature': True,
                    'observation_history': [],
                    'coupon_memory': Decimal("0.0"),
                    'put_knocked_in': False,
                    'autocalled': False,
                    'autocall_date': None,
                    'settled': False,
                }
            },
            time=datetime(2024, 4, 15)
        )

        result = compute_observation(view, 'AUTO', datetime(2024, 4, 15), spot=80.0)

        # All moves should have matching source/dest
        for move in result.moves:
            assert move.source == 'bank'
            assert move.dest == 'investor'
            assert move.quantity > 0

    def test_autocall_total_equals_notional_plus_coupon(self):
        """Autocall payout equals notional + coupon."""
        view = FakeView(
            balances={'bank': {'USD': Decimal("1000000")}, 'investor': {'AUTO': Decimal("1")}},
            states={
                'AUTO': {
                    'underlying': 'SPX',
                    'notional': Decimal("100000.0"),
                    'initial_spot': Decimal("100.0"),
                    'autocall_barrier': Decimal("1.0"),
                    'coupon_barrier': Decimal("0.7"),
                    'coupon_rate': Decimal("0.08"),
                    'put_barrier': Decimal("0.6"),
                    'issue_date': datetime(2024, 1, 15),
                    'maturity_date': datetime(2025, 1, 15),
                    'observation_schedule': [datetime(2024, 4, 15)],
                    'currency': 'USD',
                    'issuer_wallet': 'bank',
                    'holder_wallet': 'investor',
                    'memory_feature': True,
                    'observation_history': [],
                    'coupon_memory': Decimal("0.0"),
                    'put_knocked_in': False,
                    'autocalled': False,
                    'autocall_date': None,
                    'settled': False,
                }
            },
            time=datetime(2024, 4, 15)
        )

        result = compute_observation(view, 'AUTO', datetime(2024, 4, 15), spot=100.0)

        expected = 100000.0 + 100000.0 * 0.08  # notional + coupon
        assert result.moves[0].quantity == expected

    def test_maturity_with_knockin_conserves_value(self):
        """Maturity payout with knock-in follows performance."""
        view = FakeView(
            balances={'bank': {'USD': Decimal("1000000")}, 'investor': {'AUTO': Decimal("1")}},
            states={
                'AUTO': {
                    'underlying': 'SPX',
                    'notional': Decimal("100000.0"),
                    'initial_spot': Decimal("100.0"),
                    'autocall_barrier': Decimal("1.0"),
                    'coupon_barrier': Decimal("0.7"),
                    'coupon_rate': Decimal("0.08"),
                    'put_barrier': Decimal("0.6"),
                    'issue_date': datetime(2024, 1, 15),
                    'maturity_date': datetime(2025, 1, 15),
                    'observation_schedule': [datetime(2024, 4, 15)],
                    'currency': 'USD',
                    'issuer_wallet': 'bank',
                    'holder_wallet': 'investor',
                    'memory_feature': True,
                    'observation_history': [],
                    'coupon_memory': Decimal("0.0"),
                    'put_knocked_in': True,
                    'autocalled': False,
                    'autocall_date': None,
                    'settled': False,
                }
            },
            time=datetime(2025, 1, 15)
        )

        final_spot = 75.0
        result = compute_maturity_payoff(view, 'AUTO', final_spot=final_spot)

        expected = 100000.0 * (final_spot / 100.0)
        assert result.moves[0].quantity == expected
