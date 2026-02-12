"""
Volume Profile calculator.

Distributes traded volume across price bins to identify:
    - **POC** (Point of Control) — price level with the most volume.
    - **Value Area** — price range containing 70% of total volume.
    - **HVN walls** — High Volume Nodes acting as support/resistance.

Bin sizing uses the Freedman-Diaconis rule for data-adaptive widths.

Usage:
    from analyst.volume_profile import calculate_volume_profile, find_hvn_walls

    profile = calculate_volume_profile(candles)
    walls   = find_hvn_walls(profile, spot_price=1850.0)
"""

import logging
import math
from collections import defaultdict

import numpy as np
import pandas as pd

import config

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Bin sizing
# ──────────────────────────────────────────────

def _freedman_diaconis_bin_width(closes: pd.Series) -> float:
    """
    Compute optimal histogram bin width via the Freedman-Diaconis rule.

    Formula: bin_width = 2 × IQR × n^(-1/3)

    This adapts automatically to data spread:
    - Tight consolidation → small bins → fine-grained VP
    - Wide trending range → large bins → avoids noise

    Falls back to 0.5% of median price if IQR is zero.
    """
    q75, q25 = np.percentile(closes.dropna(), [75, 25])
    iqr = q75 - q25
    n = len(closes)

    if iqr == 0 or n == 0:
        # Fallback for dead stocks with no price movement
        fallback = max(1.0, round(float(closes.median()) * 0.005, 2))
        logger.debug("IQR=0, falling back to bin_width=%.2f", fallback)
        return fallback

    bin_width = 2.0 * iqr * (n ** (-1.0 / 3.0))

    # Clamp to sensible range [0.5, 200] to prevent degenerate cases
    bin_width = max(0.5, min(200.0, bin_width))

    return round(bin_width, 2)


# ──────────────────────────────────────────────
# Volume Profile
# ──────────────────────────────────────────────

def calculate_volume_profile(
    candles: list[dict],
    bin_size: float | None = None,
) -> dict | None:
    """
    Build a Volume Profile from daily candle data.

    For each candle, volume is distributed uniformly across the
    price bins spanned by [low, high].

    Parameters
    ----------
    candles : list[dict]
        Daily candles with keys: open, high, low, close, volume.
    bin_size : float or None
        Price bin width. If None, computed via Freedman-Diaconis rule.

    Returns
    -------
    dict or None
        {
            'bins': dict[float, float],   — {bin_price: accumulated_volume}
            'poc': float,                  — Point of Control price
            'va_high': float,              — Value Area upper bound
            'va_low': float,               — Value Area lower bound
            'total_volume': float,
            'bin_size': float,
            'adv': float,                  — Average Daily Volume
        }
        Returns None if candles are insufficient or ADV too low.
    """
    if not candles or len(candles) < 10:
        logger.warning("Insufficient candles for VP: got %d.", len(candles))
        return None

    # ── Check Average Daily Volume ──
    volumes = [c["volume"] for c in candles if c.get("volume", 0) > 0]
    if not volumes:
        logger.warning("All candles have zero volume.")
        return None

    adv = sum(volumes) / len(volumes)
    if adv < config.VP_MIN_ADV:
        logger.info(
            "ADV = %.0f < threshold %d — skipping (dead stock).",
            adv, config.VP_MIN_ADV,
        )
        return None

    # ── Compute bin size ──
    closes = pd.Series([c["close"] for c in candles], dtype=float)
    if bin_size is None:
        bin_size = _freedman_diaconis_bin_width(closes)
    logger.debug("Using bin_size = %.2f", bin_size)

    # ── Distribute volume across bins ──
    bins: dict[float, float] = defaultdict(float)

    for candle in candles:
        high = candle["high"]
        low = candle["low"]
        vol = candle.get("volume", 0)

        if vol <= 0 or high <= low:
            continue

        # Number of bins this candle spans
        low_bin = math.floor(low / bin_size) * bin_size
        high_bin = math.floor(high / bin_size) * bin_size
        num_bins = max(1, round((high_bin - low_bin) / bin_size) + 1)
        vol_per_bin = vol / num_bins

        price = low_bin
        while price <= high_bin + bin_size * 0.01:  # small epsilon for float
            bins[round(price, 2)] += vol_per_bin
            price += bin_size

    if not bins:
        logger.warning("No volume bins generated.")
        return None

    total_volume = sum(bins.values())

    # ── Point of Control (POC) ──
    poc_price = max(bins, key=bins.get)

    # ── Value Area (70%) ──
    va_high, va_low = _compute_value_area(bins, poc_price, bin_size, total_volume)

    return {
        "bins": dict(sorted(bins.items())),
        "poc": poc_price,
        "va_high": va_high,
        "va_low": va_low,
        "total_volume": total_volume,
        "bin_size": bin_size,
        "adv": round(adv, 0),
    }


def _compute_value_area(
    bins: dict[float, float],
    poc: float,
    bin_size: float,
    total_volume: float,
) -> tuple[float, float]:
    """
    Expand outward from POC until 70% of total volume is captured.

    Alternately expands up and down, always taking the side that
    adds more volume, matching the standard TPO value area algorithm.
    """
    target_volume = total_volume * (config.VP_VALUE_AREA_PCT / 100.0)
    accumulated = bins.get(poc, 0.0)

    sorted_prices = sorted(bins.keys())
    poc_idx = min(range(len(sorted_prices)), key=lambda i: abs(sorted_prices[i] - poc))

    upper_idx = poc_idx + 1
    lower_idx = poc_idx - 1

    va_high = poc
    va_low = poc

    while accumulated < target_volume:
        vol_up = 0.0
        vol_down = 0.0

        if upper_idx < len(sorted_prices):
            vol_up = bins.get(sorted_prices[upper_idx], 0.0)
        if lower_idx >= 0:
            vol_down = bins.get(sorted_prices[lower_idx], 0.0)

        if vol_up == 0.0 and vol_down == 0.0:
            break  # No more bins to expand into

        if vol_up >= vol_down:
            accumulated += vol_up
            va_high = sorted_prices[upper_idx]
            upper_idx += 1
        else:
            accumulated += vol_down
            va_low = sorted_prices[lower_idx]
            lower_idx -= 1

    return va_high, va_low


# ──────────────────────────────────────────────
# HVN Wall Detection
# ──────────────────────────────────────────────

def find_hvn_walls(
    profile: dict,
    spot_price: float,
) -> dict:
    """
    Identify High Volume Node (HVN) walls relative to the spot price.

    An HVN is any price bin with volume ≥ VP_HVN_MULTIPLIER × mean volume.

    Parameters
    ----------
    profile : dict
        Output of calculate_volume_profile().
    spot_price : float
        Current market price of the underlying.

    Returns
    -------
    dict
        {
            'support_wall': float | None,      — nearest HVN below spot
            'resistance_wall': float | None,   — nearest HVN above spot
            'all_hvns': list[float],            — all detected HVNs
        }
    """
    bins = profile["bins"]
    if not bins:
        return {"support_wall": None, "resistance_wall": None, "all_hvns": []}

    mean_vol = sum(bins.values()) / len(bins)
    hvn_threshold = mean_vol * config.VP_HVN_MULTIPLIER

    all_hvns = sorted([price for price, vol in bins.items() if vol >= hvn_threshold])

    # Nearest HVN below spot (support)
    support_candidates = [p for p in all_hvns if p < spot_price]
    support_wall = support_candidates[-1] if support_candidates else None

    # Nearest HVN above spot (resistance)
    resist_candidates = [p for p in all_hvns if p > spot_price]
    resistance_wall = resist_candidates[0] if resist_candidates else None

    logger.debug(
        "HVNs found: %d | Support wall: %s | Resistance wall: %s",
        len(all_hvns), support_wall, resistance_wall,
    )

    return {
        "support_wall": support_wall,
        "resistance_wall": resistance_wall,
        "all_hvns": all_hvns,
    }
