"""
Scanner Module — filters F&O stocks for high-probability credit spread candidates.

Pipeline
--------
1. Fetch the F&O universe (instrument master).
2. For each stock:
   a. Score it via IVP (or HV Rank fallback).
   b. Filter by score threshold.
   c. Detect trend (Bullish / Bearish via 50-day EMA).
3. Return the top 3–5 candidates sorted by score (descending).

Usage:
    from scanner.scanner import run_scan

    results = run_scan()
    # results = [
    #   {'symbol': 'RELIANCE', 'score': 75.0, 'method': 'IVP',
    #    'trend': 'Bullish', 'ema_50': 2540.3, 'spot': 2610.0,
    #    'current_iv': 0.28},
    #   ...
    # ]
"""

import logging
import random
import time
from typing import Any

import config
from core.instrument_master import get_fno_stocks, build_nse_token_map
from core.kite_client import KiteClient
from core.trend_detector import detect_trend
from scanner.iv_scorer import get_iv_score

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
MAX_CANDIDATES = 5       # Max stocks to return from the scan
MIN_SCORE = config.IVP_THRESHOLD   # Minimum IVP / HV Rank to qualify


def _validate_token(kite: KiteClient) -> bool:
    """Verify the access token is still valid."""
    try:
        kite.margins()
        return True
    except Exception as err:
        logger.error("Access token invalid: %s", err)
        return False


def run_scan(
    kite: KiteClient | None = None,
    max_candidates: int = MAX_CANDIDATES,
    min_score: float = MIN_SCORE,
) -> list[dict[str, Any]]:
    """
    Execute the full scanner pipeline and return filtered candidates.

    Parameters
    ----------
    kite : KiteClient or None
        Authenticated Kite client. If None, a new one is created.
    max_candidates : int
        Maximum number of candidates to return (default: 5).
    min_score : float
        Minimum IVP / HV Rank to pass the filter (default: from config).

    Returns
    -------
    list[dict]
        Each dict contains:
        - symbol       : str     — stock symbol
        - score        : float   — IVP or HV Rank (0–100)
        - method       : str     — 'IVP' or 'HV_RANK'
        - trend        : str     — 'Bullish' | 'Bearish' | 'Unknown'
        - ema_50       : float   — 50-day EMA value
        - spot         : float   — current market price
        - current_iv   : float   — latest ATM IV

        Sorted by score descending. Empty list if nothing qualifies.
    """
    logger.info("═══ Starting Scanner Run ═══")

    if kite is None:
        kite = KiteClient()

    if not _validate_token(kite):
        logger.error("Cannot run scanner — invalid token.")
        return []

    # ── Step 1: Fetch instrument masters ──
    fno_stocks = get_fno_stocks(kite)
    time.sleep(random.uniform(0.3, 0.8))
    nse_token_map = build_nse_token_map(kite)

    scored: list[dict[str, Any]] = []
    skipped = 0

    logger.info(
        "Scanning %d F&O stocks (min score: %.0f%%) …",
        len(fno_stocks),
        min_score,
    )

    for i, stock in enumerate(fno_stocks, 1):
        symbol = stock["symbol"]

        # ── Skip index underlyings (handled separately if needed) ──
        if symbol in ("NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"):
            continue

        nse_token = nse_token_map.get(symbol)

        # ── Step 2a: IV Score ──
        time.sleep(random.uniform(0.2, 0.5))
        iv_result = get_iv_score(
            symbol=symbol,
            kite=kite,
            nse_token=nse_token,
        )

        if iv_result is None:
            skipped += 1
            continue

        score = iv_result["score"]

        # ── Step 2b: Filter by threshold ──
        if score < min_score:
            logger.debug(
                "  %s — %s = %.1f%% (below threshold, skipping)",
                symbol,
                iv_result["method"],
                score,
            )
            skipped += 1
            continue

        # ── Step 2c: Get spot price ──
        time.sleep(random.uniform(0.2, 0.5))
        try:
            ltp_data = kite.ltp([f"NSE:{symbol}"])
            spot = ltp_data.get(f"NSE:{symbol}", {}).get("last_price")
        except Exception as exc:
            logger.warning("  LTP fetch failed for %s: %s", symbol, exc)
            skipped += 1
            continue

        if not spot:
            skipped += 1
            continue

        # ── Step 2d: Trend detection ──
        trend_data = {"trend": "Unknown", "ema_50": None, "spot": spot}
        if nse_token:
            try:
                time.sleep(random.uniform(0.2, 0.5))
                candles = kite.historical_data(nse_token, "day", 120)
                trend_data = detect_trend(candles, spot)
            except Exception as exc:
                logger.warning("  Trend detection failed for %s: %s", symbol, exc)

        candidate = {
            "symbol": symbol,
            "score": score,
            "method": iv_result["method"],
            "trend": trend_data["trend"],
            "ema_50": trend_data.get("ema_50"),
            "spot": spot,
            "current_iv": iv_result.get("current_iv"),
        }

        scored.append(candidate)
        logger.info(
            "  ✓ %s — %s = %.1f%% | Trend: %s | Spot: %.2f | EMA50: %s",
            symbol,
            iv_result["method"],
            score,
            trend_data["trend"],
            spot,
            trend_data.get("ema_50", "N/A"),
        )

    # ── Step 3: Sort and truncate ──
    scored.sort(key=lambda c: c["score"], reverse=True)
    top = scored[:max_candidates]

    logger.info(
        "═══ Scan complete: %d qualified, %d skipped, returning top %d ═══",
        len(scored),
        skipped,
        len(top),
    )

    return top
