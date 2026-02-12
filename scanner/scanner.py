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
    
    logger.info(
        "Scanning %d F&O stocks (min score: %.0f%%) in PARALLEL...",
        len(fno_stocks),
        min_score,
    )

    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Parallel processing with max_workers=10 (conservative for rate limits)
    # Kite Connect usually allows ~3 req/sec, but checks are lightweight.
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(
                _process_stock, kite, stock["symbol"], nse_token_map, min_score
            ): stock["symbol"]
            for stock in fno_stocks
            if stock["symbol"] not in (
                "NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"
            )
        }

        for future in as_completed(futures):
            symbol = futures[future]
            try:
                result = future.result()
                if result:
                    scored.append(result)
            except Exception as exc:
                logger.error("Error processing %s: %s", symbol, exc)

    # ── Step 3: Sort and truncate ──
    scored.sort(key=lambda c: c["score"], reverse=True)
    top = scored[:max_candidates]

    logger.info(
        "═══ Scan complete: %d qualified, returning top %d ═══",
        len(scored),
        len(top),
    )

    return top


def _process_stock(
    kite: KiteClient,
    symbol: str,
    nse_token_map: dict[str, int],
    min_score: float,
) -> dict[str, Any] | None:
    """Helper to process a single stock (runs in thread)."""
    nse_token = nse_token_map.get(symbol)

    # ── Step 2a: IV Score ──
    # Random sleep to prevent rigid thundering herd
    time.sleep(random.uniform(0.1, 1.0))
    
    try:
        iv_result = get_iv_score(
            symbol=symbol,
            kite=kite,
            nse_token=nse_token,
        )
    except Exception as e:
        logger.warning("IV Score failed for %s: %s", symbol, e)
        return None

    if iv_result is None:
        return None

    score = iv_result["score"]
    method = iv_result["method"]

    # ── Step 2b: Filter by threshold ──
    if score < min_score:
        return None  # Silent skip

    # ── Step 2c: Get spot price ──
    token_str = f"NSE:{symbol}"
    try:
        ltp_data = kite.ltp([token_str])
        spot = ltp_data.get(token_str, {}).get("last_price")
    except Exception as exc:
        logger.warning("LTP fetch failed for %s: %s", symbol, exc)
        return None

    if not spot:
        return None

    # ── Step 2d: Trend detection ──
    trend_data = {"trend": "Unknown", "ema_50": None, "spot": spot}
    if nse_token:
        try:
            # We need 120 days history for EMA-50
            # This is the most expensive call.
            candles = kite.historical_data(nse_token, "day", 120)
            trend_data = detect_trend(candles, spot)
        except Exception as exc:
            logger.warning("Trend detection failed for %s: %s", symbol, exc)

    candidate = {
        "symbol": symbol,
        "score": score,
        "method": method,
        "trend": trend_data["trend"],
        "ema_50": trend_data.get("ema_50"),
        "spot": spot,
        "current_iv": iv_result.get("current_iv"),
    }
    
    logger.info(
        "  ✓ %s — %s = %.1f%% | Trend: %s",
        symbol, method, score, trend_data["trend"]
    )
    return candidate
