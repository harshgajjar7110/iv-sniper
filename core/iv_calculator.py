"""
Implied Volatility (IV) calculator via Black-Scholes.

Uses Newton-Raphson to invert the Black-Scholes formula and extract
IV from the market price of an option.

Usage:
    from core.iv_calculator import implied_volatility

    iv = implied_volatility(
        option_price=120.0,
        spot=18200.0,
        strike=18200.0,
        time_to_expiry_years=0.05,
        risk_free_rate=0.07,
        option_type="CE",
    )
    # iv ≈ 0.15  →  15% implied volatility
"""

import math
from scipy.stats import norm


def _d1(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Compute Black-Scholes d1."""
    return (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))


def _d2(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Compute Black-Scholes d2."""
    return _d1(S, K, T, r, sigma) - sigma * math.sqrt(T)


def black_scholes_price(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str = "CE",
) -> float:
    """
    Calculate theoretical Black-Scholes option price.

    Parameters
    ----------
    S : float – Spot price of the underlying.
    K : float – Strike price.
    T : float – Time to expiry in years (e.g. 30/365 ≈ 0.082).
    r : float – Annualised risk-free interest rate (e.g. 0.07 for 7 %).
    sigma : float – Volatility (e.g. 0.20 for 20 %).
    option_type : str – "CE" for Call, "PE" for Put.

    Returns
    -------
    float – Theoretical option price.
    """
    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(S, K, T, r, sigma)

    if option_type.upper() == "CE":
        return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    else:  # PE
        return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def _vega(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """
    Black-Scholes Vega — sensitivity of option price to volatility.

    Used as the derivative in Newton-Raphson iteration.
    """
    d1 = _d1(S, K, T, r, sigma)
    return S * norm.pdf(d1) * math.sqrt(T)


def implied_volatility(
    option_price: float,
    spot: float,
    strike: float,
    time_to_expiry_years: float,
    risk_free_rate: float = 0.07,
    option_type: str = "CE",
    precision: float = 1e-6,
    max_iterations: int = 100,
    initial_guess: float = 0.25,
) -> float | None:
    """
    Solve for IV using Newton-Raphson on the Black-Scholes model.

    Parameters
    ----------
    option_price : float
        Market (observed) price of the option.
    spot : float
        Current price of the underlying asset.
    strike : float
        Strike price of the option.
    time_to_expiry_years : float
        Time remaining to expiry in years.
    risk_free_rate : float
        Annualised risk-free rate (default 7 % for India).
    option_type : str
        "CE" or "PE".
    precision : float
        Convergence tolerance.
    max_iterations : int
        Maximum Newton-Raphson iterations.
    initial_guess : float
        Starting sigma value.

    Returns
    -------
    float or None
        The implied volatility as a decimal, or None if the solver
        did not converge (e.g. deep ITM/OTM with no vega).
    """
    if time_to_expiry_years <= 0 or option_price <= 0:
        return None

    sigma = initial_guess

    for _ in range(max_iterations):
        bs_price = black_scholes_price(
            spot, strike, time_to_expiry_years, risk_free_rate, sigma, option_type
        )
        v = _vega(spot, strike, time_to_expiry_years, risk_free_rate, sigma)

        if v < 1e-12:
            # Vega too small — can't converge reliably
            return None

        diff = bs_price - option_price
        if abs(diff) < precision:
            return round(sigma, 6)

        sigma -= diff / v

        # Guard against sigma going negative or absurdly large
        if sigma <= 0:
            sigma = 0.001
        elif sigma > 5.0:
            return None

    return None  # Did not converge
