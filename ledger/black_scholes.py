"""
black_scholes.py - Black-Scholes Option Pricing and Greeks

Zero-rate Black-Scholes formulas with time in trading days (252 days/year).
All functions use t_in_days as the time parameter.

Provides:
- Option pricing (call, put)
- First-order Greeks (delta, theta, vega)
- Second-order Greeks (gamma, vanna, volga)
- Cross Greeks (charm, vanna, etc.)
- Implied volatility (vectorized)

Naming convention for Greeks:
- call_s = delta (∂C/∂S)
- call_t = theta (∂C/∂t) - note: positive = time decay cost
- call_v = vega (∂C/∂σ)
- call_ss = gamma (∂²C/∂S²)
- call_vv = volga (∂²C/∂σ²)
- call_sv = vanna (∂²C/∂S∂σ)
"""

import math
import numpy as np
from typing import Union
from scipy.special import erf as scipy_erf


# Type alias for scalar or array inputs
Numeric = Union[float, np.ndarray]

# Constants
TRADING_DAYS_PER_YEAR = 252.0
SQRT_2 = math.sqrt(2.0)
INV_SQRT_2PI = 1.0 / math.sqrt(2.0 * math.pi)


# ============================================================================
# NORMAL DISTRIBUTION FUNCTIONS
# ============================================================================

def normal_cdf(x: Numeric) -> Numeric:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + scipy_erf(np.asarray(x) / SQRT_2))


def normal_pdf(x: Numeric) -> Numeric:
    """Standard normal probability density function."""
    return INV_SQRT_2PI * np.exp(-0.5 * x * x)


# ============================================================================
# D1 AND D2
# ============================================================================

def _validate_bs_inputs(s: Numeric, k: Numeric, t_in_days: Numeric, v: Numeric) -> None:
    """Validate Black-Scholes inputs to prevent division by zero and NaN/Inf."""
    s_arr = np.asarray(s)
    k_arr = np.asarray(k)
    t_arr = np.asarray(t_in_days)
    v_arr = np.asarray(v)
    if not np.all(np.isfinite(s_arr)) or np.any(s_arr <= 0):
        raise ValueError("spot price must be positive and finite")
    if not np.all(np.isfinite(k_arr)) or np.any(k_arr <= 0):
        raise ValueError("strike must be positive and finite")
    if not np.all(np.isfinite(t_arr)) or np.any(t_arr <= 0):
        raise ValueError("t_in_days must be positive and finite")
    if not np.all(np.isfinite(v_arr)) or np.any(v_arr <= 0):
        raise ValueError("volatility must be positive and finite")


def d1(s: Numeric, k: Numeric, t_in_days: Numeric, v: Numeric) -> Numeric:
    """
    Calculate d1 in Black-Scholes formula (zero-rate).

    d1 = (ln(S/K) + 0.5*σ²*t) / (σ*√t)

    Raises:
        ValueError: If any input is non-positive or not finite
    """
    _validate_bs_inputs(s, k, t_in_days, v)
    t = t_in_days / TRADING_DAYS_PER_YEAR
    return (np.log(s / k) + 0.5 * v * v * t) / (v * np.sqrt(t))


def d2(s: Numeric, k: Numeric, t_in_days: Numeric, v: Numeric) -> Numeric:
    """
    Calculate d2 in Black-Scholes formula (zero-rate).

    d2 = (ln(S/K) - 0.5*σ²*t) / (σ*√t) = d1 - σ*√t

    Raises:
        ValueError: If any input is non-positive or not finite
    """
    _validate_bs_inputs(s, k, t_in_days, v)
    t = t_in_days / TRADING_DAYS_PER_YEAR
    return (np.log(s / k) - 0.5 * v * v * t) / (v * np.sqrt(t))


# ============================================================================
# OPTION PRICES
# ============================================================================

def call(s: Numeric, k: Numeric, t_in_days: Numeric, v: Numeric) -> Numeric:
    """
    Black-Scholes call option price (zero-rate).

    C = S*N(d1) - K*N(d2)
    """
    d1_val = d1(s, k, t_in_days, v)
    d2_val = d2(s, k, t_in_days, v)
    return s * normal_cdf(d1_val) - k * normal_cdf(d2_val)


def put(s: Numeric, k: Numeric, t_in_days: Numeric, v: Numeric) -> Numeric:
    """
    Black-Scholes put option price (zero-rate).

    P = K*N(-d2) - S*N(-d1)
    """
    d1_val = d1(s, k, t_in_days, v)
    d2_val = d2(s, k, t_in_days, v)
    return k * normal_cdf(-d2_val) - s * normal_cdf(-d1_val)


# ============================================================================
# CALL GREEKS - FIRST ORDER
# ============================================================================

def call_s(s: Numeric, k: Numeric, t_in_days: Numeric, v: Numeric) -> Numeric:
    """Call delta: ∂C/∂S = N(d1)"""
    return normal_cdf(d1(s, k, t_in_days, v))


def call_k(s: Numeric, k: Numeric, t_in_days: Numeric, v: Numeric) -> Numeric:
    """Call sensitivity to strike: ∂C/∂K = -N(d2)"""
    return -normal_cdf(d2(s, k, t_in_days, v))


def call_t(s: Numeric, k: Numeric, t_in_days: Numeric, v: Numeric) -> Numeric:
    """
    Call theta: ∂C/∂t per trading day

    Returns positive value representing the daily time decay cost.
    θ = S*σ*n(d1) / (2*√t)
    """
    t = t_in_days / TRADING_DAYS_PER_YEAR
    return s * v * normal_pdf(d1(s, k, t_in_days, v)) / (2.0 * math.sqrt(t))


def call_v(s: Numeric, k: Numeric, t_in_days: Numeric, v: Numeric) -> Numeric:
    """
    Call vega: ∂C/∂σ

    ν = S*n(d1)*√t
    """
    t = t_in_days / TRADING_DAYS_PER_YEAR
    return s * normal_pdf(d1(s, k, t_in_days, v)) * math.sqrt(t)


# ============================================================================
# CALL GREEKS - SECOND ORDER
# ============================================================================

def call_ss(s: Numeric, k: Numeric, t_in_days: Numeric, v: Numeric) -> Numeric:
    """
    Call gamma: ∂²C/∂S²

    Γ = n(d1) / (S*σ*√t)
    """
    t = t_in_days / TRADING_DAYS_PER_YEAR
    return normal_pdf(d1(s, k, t_in_days, v)) / (s * v * math.sqrt(t))


def call_kk(s: Numeric, k: Numeric, t_in_days: Numeric, v: Numeric) -> Numeric:
    """∂²C/∂K² = n(d2) / (K*σ*√t)"""
    t = t_in_days / TRADING_DAYS_PER_YEAR
    return normal_pdf(d2(s, k, t_in_days, v)) / (k * v * math.sqrt(t))


def call_vv(s: Numeric, k: Numeric, t_in_days: Numeric, v: Numeric) -> Numeric:
    """
    Call volga (vomma): ∂²C/∂σ²

    Volga = vega * d1 * d2 / σ
    """
    return call_v(s, k, t_in_days, v) * d1(s, k, t_in_days, v) * d2(s, k, t_in_days, v) / v


# ============================================================================
# CALL GREEKS - CROSS DERIVATIVES
# ============================================================================

def call_st(s: Numeric, k: Numeric, t_in_days: Numeric, v: Numeric) -> Numeric:
    """Call charm: ∂²C/∂S∂t = -n(d1)*d2 / (2*t)"""
    t = t_in_days / TRADING_DAYS_PER_YEAR
    return -normal_pdf(d1(s, k, t_in_days, v)) * d2(s, k, t_in_days, v) / (2.0 * t)


def call_sv(s: Numeric, k: Numeric, t_in_days: Numeric, v: Numeric) -> Numeric:
    """
    Call vanna: ∂²C/∂S∂σ

    Vanna = -n(d1)*d2 / σ
    """
    return -normal_pdf(d1(s, k, t_in_days, v)) * d2(s, k, t_in_days, v) / v


def call_kv(s: Numeric, k: Numeric, t_in_days: Numeric, v: Numeric) -> Numeric:
    """∂²C/∂K∂σ = n(d2)*d1 / σ"""
    return normal_pdf(d2(s, k, t_in_days, v)) * d1(s, k, t_in_days, v) / v


# ============================================================================
# PUT GREEKS - FIRST ORDER
# ============================================================================

def put_s(s: Numeric, k: Numeric, t_in_days: Numeric, v: Numeric) -> Numeric:
    """Put delta: ∂P/∂S = -N(-d1) = N(d1) - 1"""
    return -normal_cdf(-d1(s, k, t_in_days, v))


def put_k(s: Numeric, k: Numeric, t_in_days: Numeric, v: Numeric) -> Numeric:
    """Put sensitivity to strike: ∂P/∂K = N(-d2)"""
    return normal_cdf(-d2(s, k, t_in_days, v))


def put_t(s: Numeric, k: Numeric, t_in_days: Numeric, v: Numeric) -> Numeric:
    """
    Put theta: ∂P/∂t per trading day

    Returns positive value representing the daily time decay cost.
    θ = S*σ*n(d1) / (2*√t)
    """
    t = t_in_days / TRADING_DAYS_PER_YEAR
    return s * v * normal_pdf(d1(s, k, t_in_days, v)) / (2.0 * math.sqrt(t))


def put_v(s: Numeric, k: Numeric, t_in_days: Numeric, v: Numeric) -> Numeric:
    """
    Put vega: ∂P/∂σ

    ν = S*n(d1)*√t
    """
    t = t_in_days / TRADING_DAYS_PER_YEAR
    return s * normal_pdf(d1(s, k, t_in_days, v)) * math.sqrt(t)


# ============================================================================
# PUT GREEKS - SECOND ORDER
# ============================================================================

def put_ss(s: Numeric, k: Numeric, t_in_days: Numeric, v: Numeric) -> Numeric:
    """
    Put gamma: ∂²P/∂S²

    Γ = n(d1) / (S*σ*√t)
    """
    t = t_in_days / TRADING_DAYS_PER_YEAR
    return normal_pdf(d1(s, k, t_in_days, v)) / (s * v * math.sqrt(t))


def put_kk(s: Numeric, k: Numeric, t_in_days: Numeric, v: Numeric) -> Numeric:
    """∂²P/∂K²"""
    t = t_in_days / TRADING_DAYS_PER_YEAR
    return normal_pdf(d2(s, k, t_in_days, v)) / (k * v * math.sqrt(t))


def put_vv(s: Numeric, k: Numeric, t_in_days: Numeric, v: Numeric) -> Numeric:
    """
    Put volga (vomma): ∂²P/∂σ²

    Volga = vega * d1 * d2 / σ
    """
    return put_v(s, k, t_in_days, v) * d1(s, k, t_in_days, v) * d2(s, k, t_in_days, v) / v


# ============================================================================
# PUT GREEKS - CROSS DERIVATIVES
# ============================================================================

def put_st(s: Numeric, k: Numeric, t_in_days: Numeric, v: Numeric) -> Numeric:
    """Put charm: ∂²P/∂S∂t"""
    t = t_in_days / TRADING_DAYS_PER_YEAR
    return -normal_pdf(d1(s, k, t_in_days, v)) * d2(s, k, t_in_days, v) / (2.0 * t)


def put_sv(s: Numeric, k: Numeric, t_in_days: Numeric, v: Numeric) -> Numeric:
    """
    Put vanna: ∂²P/∂S∂σ

    Vanna = -n(d1)*d2 / σ
    """
    return -normal_pdf(d1(s, k, t_in_days, v)) * d2(s, k, t_in_days, v) / v


def put_kv(s: Numeric, k: Numeric, t_in_days: Numeric, v: Numeric) -> Numeric:
    """∂²P/∂K∂σ"""
    return normal_pdf(d2(s, k, t_in_days, v)) * d1(s, k, t_in_days, v) / v


# ============================================================================
# IMPLIED VOLATILITY
# ============================================================================

def call_impvol(
    s: float,
    k: Union[float, np.ndarray],
    t_in_days: float,
    p: Union[float, np.ndarray]
) -> Union[float, np.ndarray]:
    """
    Calculate implied volatility for call options using binary search.

    Vectorized implementation that handles arrays of strikes and prices.

    Args:
        s: Current stock/forward price
        k: Strike price(s) - scalar or array
        t_in_days: Time to expiry in trading days
        p: Call option price(s) to find implied vol for - scalar or array

    Returns:
        Implied volatility (scalar or array matching input shape)
    """
    # Convert to arrays for uniform handling
    k_arr = np.atleast_1d(k)
    p_arr = np.atleast_1d(p)

    # Initialize lower and upper volatility bounds
    v_d = np.full_like(k_arr, 0.0001, dtype=float)  # Lower bound of 0.01%
    v_u = np.full_like(k_arr, 5.0, dtype=float)      # Upper bound of 500%

    # Initial midpoint guess
    v_m = (v_d + v_u) / 2.0
    call_m = call(s, k_arr, t_in_days, v_m)

    # Binary search iteration
    for _ in range(25):  # 25 iterations gives ~1e-8 precision
        # Compare arrays element-wise
        diff = call_m - p_arr
        mask = diff > 0  # True where midpoint price > target price

        # Update bounds based on mask
        v_u = np.where(mask, v_m, v_u)  # Update upper bound where price too high
        v_d = np.where(mask, v_d, v_m)  # Update lower bound where price too low

        # New midpoint
        v_m = (v_d + v_u) / 2.0
        call_m = call(s, k_arr, t_in_days, v_m)

    # Return scalar if input was scalar
    if np.isscalar(k) and np.isscalar(p):
        return float(v_m[0])
    return v_m


def put_impvol(
    s: float,
    k: Union[float, np.ndarray],
    t_in_days: float,
    p: Union[float, np.ndarray]
) -> Union[float, np.ndarray]:
    """
    Calculate implied volatility for put options using binary search.

    Vectorized implementation that handles arrays of strikes and prices.

    Args:
        s: Current stock/forward price
        k: Strike price(s) - scalar or array
        t_in_days: Time to expiry in trading days
        p: Put option price(s) to find implied vol for - scalar or array

    Returns:
        Implied volatility (scalar or array matching input shape)
    """
    # Convert to arrays for uniform handling
    k_arr = np.atleast_1d(k)
    p_arr = np.atleast_1d(p)

    # Initialize lower and upper volatility bounds
    v_d = np.full_like(k_arr, 0.0001, dtype=float)  # Lower bound of 0.01%
    v_u = np.full_like(k_arr, 5.0, dtype=float)      # Upper bound of 500%

    # Initial midpoint guess
    v_m = (v_d + v_u) / 2.0
    put_m = put(s, k_arr, t_in_days, v_m)

    # Binary search iteration
    for _ in range(25):  # 25 iterations gives ~1e-8 precision
        # Compare arrays element-wise
        diff = put_m - p_arr
        mask = diff > 0  # True where midpoint price > target price

        # Update bounds based on mask
        v_u = np.where(mask, v_m, v_u)  # Update upper bound where price too high
        v_d = np.where(mask, v_d, v_m)  # Update lower bound where price too low

        # New midpoint
        v_m = (v_d + v_u) / 2.0
        put_m = put(s, k_arr, t_in_days, v_m)

    # Return scalar if input was scalar
    if np.isscalar(k) and np.isscalar(p):
        return float(v_m[0])
    return v_m


# ============================================================================
# STANDARD GREEK ALIASES
# ============================================================================

# Call Greeks
call_delta = call_s
call_theta = call_t
call_vega = call_v
call_gamma = call_ss
call_vanna = call_sv
call_volga = call_vv
call_charm = call_st

# Put Greeks
put_delta = put_s
put_theta = put_t
put_vega = put_v
put_gamma = put_ss
put_vanna = put_sv
put_volga = put_vv
put_charm = put_st

# Shared Greeks
gamma = call_ss
vega = call_v
vanna = call_sv
volga = call_vv


if __name__ == "__main__":
    # Simple test cases
    S = 100.0  # Underlying price
    K = 100.0  # Strike price
    t = 252.0  # Time to expiry in days (1 year)
    sigma = 0.2  # Volatility (20%)

    call_price = call(S, K, t, sigma)
    put_price = put(S, K, t, sigma)

    print(f"Call Price: {call_price:.4f}")
    print(f"Put Price: {put_price:.4f}")

    call_iv = call_impvol(S, K, t, call_price)
    put_iv = put_impvol(S, K, t, put_price)

    print(f"Call Implied Volatility: {call_iv:.4f}")
    print(f"Put Implied Volatility: {put_iv:.4f}")