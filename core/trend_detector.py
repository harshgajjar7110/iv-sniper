"""
Trend Detection via Exponential Moving Average (EMA).

Determines whether a stock is in a Bullish or Bearish regime
by comparing its current price against its 50-day EMA.

Usage:
    from core.trend_detector import detect_trend

    result = detect_trend(candles, spot_price)
    # result = {'trend': 'Bullish', 'ema_50': 1825.3, 'spot': 1870.0}
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def compute_ema(
    candles: list[dict],
    span: int = 50,
) -> float | None:
    """
    Compute the Exponential Moving Average of closing prices.

    Parameters
    ----------
    candles : list[dict]
        Daily candles with a 'close' key (from KiteClient.historical_data).
    span : int
        EMA lookback period (default: 50 days).

    Returns
    -------
    float or None
        The latest EMA value, or None if insufficient data.
    """
    if len(candles) < span:
        logger.warning(
            "Need at least %d candles for %d-day EMA; got %d.",
            span, span, len(candles),
        )
        return None

    closes = pd.Series([c["close"] for c in candles], dtype=float)
    ema = closes.ewm(span=span, adjust=False).mean()
    return round(float(ema.iloc[-1]), 2)


def detect_trend(
    candles: list[dict],
    spot_price: float,
    ema_span: int = 50,
) -> dict:
    """
    Determine Bullish or Bearish trend for a stock.

    Logic
    -----
    - **Bullish**: Spot price > 50-day EMA
    - **Bearish**: Spot price ≤ 50-day EMA

    Parameters
    ----------
    candles : list[dict]
        Daily candles with 'close' key.
    spot_price : float
        Current market price of the underlying.
    ema_span : int
        EMA lookback period.

    Returns
    -------
    dict
        {'trend': 'Bullish'|'Bearish'|'Unknown', 'ema_50': float|None, 'spot': float}
    """
    ema_value = compute_ema(candles, span=ema_span)

    if ema_value is None:
        return {"trend": "Unknown", "ema_50": None, "spot": spot_price}

    trend = "Bullish" if spot_price > ema_value else "Bearish"

    return {
        "trend": trend,
        "ema_50": ema_value,
        "spot": spot_price,
    }
