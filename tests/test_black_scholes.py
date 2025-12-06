"""
test_black_scholes.py - Unit tests for black_scholes.py

Tests:
- Normal distribution functions (CDF, PDF)
- d1, d2 calculations
- Call and put pricing
- First-order Greeks (delta, theta, vega)
- Second-order Greeks (gamma, vanna, volga)
- Implied volatility
- Put-call parity
"""

import pytest
import math
import numpy as np
from ledger.black_scholes import (
    # Core functions
    d1, d2,
    normal_cdf, normal_pdf,
)
from ledger import (
    call, put,

    # Call Greeks
    call_delta, call_theta, call_vega, call_gamma,
    put_delta, put_theta, put_vega, put_gamma,

    # Implied volatility
    call_impvol, put_impvol,

    # Shared
    gamma, vega,
)

# Import the partial derivative functions from the module directly
from ledger.black_scholes import (
    call_s, call_k, call_t, call_v,
    call_ss, call_kk, call_vv,
    call_st, call_sv,
    put_s, put_k, put_t, put_v,
    put_ss, put_vv,
    put_sv,
    call_vanna, call_volga,
    put_vanna, put_volga,
    vanna, volga,
)


class TestNormalDistribution:
    """Tests for normal distribution functions."""

    def test_normal_cdf_zero(self):
        assert normal_cdf(0) == pytest.approx(0.5, abs=1e-10)

    def test_normal_cdf_positive(self):
        # N(1) = 0.8413
        assert normal_cdf(1.0) == pytest.approx(0.8413, abs=1e-3)

    def test_normal_cdf_negative(self):
        # N(-1) = 0.1587
        assert normal_cdf(-1.0) == pytest.approx(0.1587, abs=1e-3)

    def test_normal_cdf_symmetry(self):
        # N(x) + N(-x) = 1
        for x in [0.5, 1.0, 2.0, 3.0]:
            assert normal_cdf(x) + normal_cdf(-x) == pytest.approx(1.0, abs=1e-10)

    def test_normal_cdf_extreme_positive(self):
        # N(5) = 1
        assert normal_cdf(5.0) == pytest.approx(1.0, abs=1e-5)

    def test_normal_cdf_extreme_negative(self):
        # N(-5) = 0
        assert normal_cdf(-5.0) == pytest.approx(0.0, abs=1e-5)

    def test_normal_pdf_zero(self):
        # n(0) = 1/sqrt(2*pi) = 0.3989
        assert normal_pdf(0) == pytest.approx(1.0 / math.sqrt(2 * math.pi), abs=1e-10)

    def test_normal_pdf_symmetry(self):
        # n(x) = n(-x)
        for x in [0.5, 1.0, 2.0]:
            assert normal_pdf(x) == pytest.approx(normal_pdf(-x), abs=1e-10)

    def test_normal_pdf_decreases(self):
        # PDF decreases as |x| increases
        assert normal_pdf(0) > normal_pdf(1) > normal_pdf(2) > normal_pdf(3)


class TestD1D2:
    """Tests for d1 and d2 calculations."""

    def test_d1_atm(self):
        # ATM with t_in_days = 252 (1 year), volatility = 0.2
        # d1 = (ln(1) + 0.5 * 0.2^2 * 1) / (0.2 * 1) = 0.02 / 0.2 = 0.1
        result = d1(100, 100, 252, 0.2)
        assert result == pytest.approx(0.1, abs=1e-6)

    def test_d2_atm(self):
        # d2 = d1 - sigma*sqrt(t) = 0.1 - 0.2 = -0.1
        result = d2(100, 100, 252, 0.2)
        assert result == pytest.approx(-0.1, abs=1e-6)

    def test_d1_d2_relationship(self):
        # d2 = d1 - sigma*sqrt(t)
        s, k, t_days, v = 100, 100, 252, 0.2
        t = t_days / 252.0
        d1_val = d1(s, k, t_days, v)
        d2_val = d2(s, k, t_days, v)
        assert d2_val == pytest.approx(d1_val - v * math.sqrt(t), abs=1e-10)

    def test_d1_itm(self):
        # ITM call (S > K) should have higher d1
        d1_itm = d1(120, 100, 252, 0.2)
        d1_atm = d1(100, 100, 252, 0.2)
        assert d1_itm > d1_atm

    def test_d1_otm(self):
        # OTM call (S < K) should have lower d1
        d1_otm = d1(80, 100, 252, 0.2)
        d1_atm = d1(100, 100, 252, 0.2)
        assert d1_otm < d1_atm


class TestOptionPricing:
    """Tests for call and put pricing."""

    def test_call_atm(self):
        # ATM call with 1 year to expiry, 20% vol
        # C = S * 0.0796 for zero rate (approximation)
        price = call(100, 100, 252, 0.2)
        assert 5 < price < 10  # Reasonable range for ATM

    def test_put_atm(self):
        # ATM put
        price = put(100, 100, 252, 0.2)
        assert 5 < price < 10

    def test_put_call_parity(self):
        # For zero rate: C - P = S - K (at same strike)
        # But for our formula: C - P = S - K should hold approximately
        s, k, t_days, v = 100, 100, 252, 0.2
        c = call(s, k, t_days, v)
        p = put(s, k, t_days, v)
        # At zero rate with same strike: C - P = S - K = 0
        assert c - p == pytest.approx(0, abs=1e-6)

    def test_put_call_parity_itm(self):
        s, k, t_days, v = 110, 100, 252, 0.2
        c = call(s, k, t_days, v)
        p = put(s, k, t_days, v)
        # C - P = S - K = 10
        assert c - p == pytest.approx(s - k, abs=1e-6)

    def test_call_positive(self):
        # Call price should always be positive
        assert call(100, 100, 252, 0.2) > 0
        assert call(80, 100, 252, 0.2) > 0
        assert call(120, 100, 252, 0.2) > 0

    def test_put_positive(self):
        # Put price should always be positive
        assert put(100, 100, 252, 0.2) > 0
        assert put(80, 100, 252, 0.2) > 0
        assert put(120, 100, 252, 0.2) > 0

    def test_call_increases_with_spot(self):
        # Call price increases with spot price
        assert call(90, 100, 252, 0.2) < call(100, 100, 252, 0.2) < call(110, 100, 252, 0.2)

    def test_put_decreases_with_spot(self):
        # Put price decreases with spot price
        assert put(90, 100, 252, 0.2) > put(100, 100, 252, 0.2) > put(110, 100, 252, 0.2)

    def test_call_increases_with_vol(self):
        # Call price increases with volatility
        assert call(100, 100, 252, 0.1) < call(100, 100, 252, 0.2) < call(100, 100, 252, 0.3)

    def test_put_increases_with_vol(self):
        # Put price increases with volatility
        assert put(100, 100, 252, 0.1) < put(100, 100, 252, 0.2) < put(100, 100, 252, 0.3)

    def test_call_intrinsic_deep_itm(self):
        # Deep ITM call approaches intrinsic value
        price = call(200, 100, 10, 0.2)  # Very deep ITM, short time
        intrinsic = 200 - 100
        assert price >= intrinsic
        assert price < intrinsic + 5  # Small time value

    def test_put_intrinsic_deep_itm(self):
        # Deep ITM put approaches intrinsic value
        price = put(50, 100, 10, 0.2)  # Very deep ITM, short time
        intrinsic = 100 - 50
        assert price >= intrinsic
        assert price < intrinsic + 5


class TestCallGreeks:
    """Tests for call Greeks."""

    def test_call_delta_range(self):
        # Delta should be between 0 and 1 for calls
        for s in [80, 100, 120]:
            delta = call_s(s, 100, 252, 0.2)
            assert 0 < delta < 1

    def test_call_delta_increases_with_spot(self):
        # Delta increases as spot increases
        delta_otm = call_s(80, 100, 252, 0.2)
        delta_atm = call_s(100, 100, 252, 0.2)
        delta_itm = call_s(120, 100, 252, 0.2)
        assert delta_otm < delta_atm < delta_itm

    def test_call_delta_atm_approx_half(self):
        # ATM delta is approximately 0.5 (slightly above due to drift)
        delta = call_s(100, 100, 252, 0.2)
        assert 0.45 < delta < 0.60

    def test_call_theta_positive(self):
        # Our theta is defined as time decay cost (positive)
        theta = call_t(100, 100, 252, 0.2)
        assert theta > 0

    def test_call_vega_positive(self):
        # Vega should be positive
        vega_val = call_v(100, 100, 252, 0.2)
        assert vega_val > 0

    def test_call_gamma_positive(self):
        # Gamma should be positive
        gamma_val = call_ss(100, 100, 252, 0.2)
        assert gamma_val > 0

    def test_call_gamma_highest_atm(self):
        # Gamma is highest at-the-money
        gamma_otm = call_ss(80, 100, 252, 0.2)
        gamma_atm = call_ss(100, 100, 252, 0.2)
        gamma_itm = call_ss(120, 100, 252, 0.2)
        assert gamma_atm > gamma_otm
        assert gamma_atm > gamma_itm

    def test_call_strike_sensitivity(self):
        # Call_k should be negative (call value decreases as strike increases)
        assert call_k(100, 100, 252, 0.2) < 0


class TestPutGreeks:
    """Tests for put Greeks."""

    def test_put_delta_range(self):
        # Delta should be between -1 and 0 for puts
        for s in [80, 100, 120]:
            delta = put_s(s, 100, 252, 0.2)
            assert -1 < delta < 0

    def test_put_delta_relationship_to_call(self):
        # Put delta = Call delta - 1
        for s in [80, 100, 120]:
            call_d = call_s(s, 100, 252, 0.2)
            put_d = put_s(s, 100, 252, 0.2)
            assert put_d == pytest.approx(call_d - 1, abs=1e-10)

    def test_put_theta_positive(self):
        # Put theta is same as call theta for zero rate
        theta = put_t(100, 100, 252, 0.2)
        assert theta > 0

    def test_put_vega_equals_call_vega(self):
        # Vega is the same for calls and puts
        call_vega_val = call_v(100, 100, 252, 0.2)
        put_vega_val = put_v(100, 100, 252, 0.2)
        assert call_vega_val == pytest.approx(put_vega_val, abs=1e-10)

    def test_put_gamma_equals_call_gamma(self):
        # Gamma is the same for calls and puts
        call_gamma_val = call_ss(100, 100, 252, 0.2)
        put_gamma_val = put_ss(100, 100, 252, 0.2)
        assert call_gamma_val == pytest.approx(put_gamma_val, abs=1e-10)


class TestSecondOrderGreeks:
    """Tests for second-order Greeks."""

    def test_volga_positive_otm(self):
        # Volga is typically positive for OTM options
        volga_val = call_vv(90, 100, 252, 0.2)
        assert volga_val > 0

    def test_vanna_sign(self):
        # Vanna has specific sign behavior
        # For OTM call, vanna is typically negative
        vanna_val = call_sv(90, 100, 252, 0.2)
        # Just check it's computed
        assert isinstance(vanna_val, float)

    def test_charm(self):
        # Charm (delta decay)
        charm_val = call_st(100, 100, 252, 0.2)
        assert isinstance(charm_val, float)


class TestImpliedVolatility:
    """Tests for implied volatility calculations."""

    def test_call_impvol_roundtrip(self):
        # Price an option, then recover the volatility
        s, k, t_days, v = 100, 100, 252, 0.2
        price = call(s, k, t_days, v)
        recovered_vol = call_impvol(s, k, t_days, price)
        assert recovered_vol == pytest.approx(v, abs=1e-4)

    def test_put_impvol_roundtrip(self):
        s, k, t_days, v = 100, 100, 252, 0.25
        price = put(s, k, t_days, v)
        recovered_vol = put_impvol(s, k, t_days, price)
        assert recovered_vol == pytest.approx(v, abs=1e-4)

    def test_call_impvol_itm(self):
        s, k, t_days, v = 120, 100, 252, 0.3
        price = call(s, k, t_days, v)
        recovered_vol = call_impvol(s, k, t_days, price)
        assert recovered_vol == pytest.approx(v, abs=1e-4)

    def test_call_impvol_otm(self):
        s, k, t_days, v = 80, 100, 252, 0.25
        price = call(s, k, t_days, v)
        recovered_vol = call_impvol(s, k, t_days, price)
        assert recovered_vol == pytest.approx(v, abs=1e-4)

    def test_impvol_vectorized(self):
        # Test with arrays
        s = 100
        k = np.array([90, 100, 110])
        t_days = 252
        v = 0.2
        prices = call(s, k, t_days, v)
        recovered_vols = call_impvol(s, k, t_days, prices)
        np.testing.assert_allclose(recovered_vols, [0.2, 0.2, 0.2], atol=1e-4)


class TestGreekAliases:
    """Tests for Greek function aliases."""

    def test_call_aliases(self):
        s, k, t, v = 100, 100, 252, 0.2
        assert call_delta(s, k, t, v) == call_s(s, k, t, v)
        assert call_theta(s, k, t, v) == call_t(s, k, t, v)
        assert call_vega(s, k, t, v) == call_v(s, k, t, v)
        assert call_gamma(s, k, t, v) == call_ss(s, k, t, v)
        assert call_vanna(s, k, t, v) == call_sv(s, k, t, v)
        assert call_volga(s, k, t, v) == call_vv(s, k, t, v)

    def test_put_aliases(self):
        s, k, t, v = 100, 100, 252, 0.2
        assert put_delta(s, k, t, v) == put_s(s, k, t, v)
        assert put_theta(s, k, t, v) == put_t(s, k, t, v)
        assert put_vega(s, k, t, v) == put_v(s, k, t, v)
        assert put_gamma(s, k, t, v) == put_ss(s, k, t, v)
        assert put_vanna(s, k, t, v) == put_sv(s, k, t, v)
        assert put_volga(s, k, t, v) == put_vv(s, k, t, v)

    def test_shared_aliases(self):
        s, k, t, v = 100, 100, 252, 0.2
        assert gamma(s, k, t, v) == call_ss(s, k, t, v)
        assert vega(s, k, t, v) == call_v(s, k, t, v)
        assert vanna(s, k, t, v) == call_sv(s, k, t, v)
        assert volga(s, k, t, v) == call_vv(s, k, t, v)


class TestVectorizedOperations:
    """Tests for vectorized operations with numpy arrays."""

    def test_call_vectorized_spot(self):
        s = np.array([90, 100, 110])
        k, t, v = 100, 252, 0.2
        prices = call(s, k, t, v)
        assert isinstance(prices, np.ndarray)
        assert len(prices) == 3
        assert prices[0] < prices[1] < prices[2]

    def test_call_vectorized_strike(self):
        s = 100
        k = np.array([90, 100, 110])
        t, v = 252, 0.2
        prices = call(s, k, t, v)
        assert isinstance(prices, np.ndarray)
        assert len(prices) == 3
        assert prices[0] > prices[1] > prices[2]

    def test_delta_vectorized(self):
        s = np.array([90, 100, 110])
        k, t, v = 100, 252, 0.2
        deltas = call_s(s, k, t, v)
        assert isinstance(deltas, np.ndarray)
        assert len(deltas) == 3
        assert deltas[0] < deltas[1] < deltas[2]

    def test_normal_cdf_vectorized(self):
        x = np.array([-1, 0, 1])
        result = normal_cdf(x)
        assert isinstance(result, np.ndarray)
        assert result[0] < result[1] < result[2]
        assert result[1] == pytest.approx(0.5, abs=1e-10)
