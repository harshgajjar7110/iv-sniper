"""
Historical Volatility (HV) calculator.

Methodology
-----------
1. Compute daily log-returns from closing prices.
2. Take the standard deviation of the most recent `window` returns.
3. Annualise by multiplying with √(trading-days-per-year).

Usage:
    from core.hv_calculator import calculate_hv

    hv = calculate_hv(historical_candles, window=20)
    # hv ≈ 0.32  →  32% annualised volatility
"""

import math

import numpy as np
import pandas as pd

import config


def calculate_hv(
    candles: list[dict],
    window: int = config.HV_LOOKBACK_DAYS,
) -> float:
    """
    Calculate annualised historical volatility from daily candles.

    Parameters
    ----------
    candles : list[dict]
        Output of KiteClient.historical_data() — each dict must contain
        a 'close' key at minimum.
    window : int
        Rolling window size for the standard deviation (default: 20).

    Returns
    -------
    float
        Annualised volatility as a decimal (e.g. 0.35 = 35 %).

    Raises
    ------
    ValueError
        If there are fewer candles than `window + 1` (need at least
        `window` returns, which requires `window + 1` prices).
    """
    if len(candles) < window + 1:
        raise ValueError(
            f"Need at least {window + 1} candles to compute HV "
            f"with a {window}-day window; got {len(candles)}."
        )

    closes = pd.Series([c["close"] for c in candles], dtype=float)

    # Daily log-returns: ln(P_t / P_{t-1})
    log_returns = np.log(closes / closes.shift(1)).dropna()

    # Standard deviation of the most recent `window` returns
    recent_std = log_returns.iloc[-window:].std(ddof=1)

    # Annualise
    annualised_hv = recent_std * math.sqrt(config.TRADING_DAYS_PER_YEAR)

    return round(float(annualised_hv), 6)


def calculate_hv_series(
    candles: list[dict],
    window: int = config.HV_LOOKBACK_DAYS,
) -> pd.Series:
    """
    Return a rolling HV series for the full candle history.

    Useful for computing HV Rank (min / max over 1 year).
    """
    closes = pd.Series([c["close"] for c in candles], dtype=float)
    log_returns = np.log(closes / closes.shift(1)).dropna()

    rolling_std = log_returns.rolling(window=window).std(ddof=1)
    rolling_hv = rolling_std * math.sqrt(config.TRADING_DAYS_PER_YEAR)

    return rolling_hv.dropna()
