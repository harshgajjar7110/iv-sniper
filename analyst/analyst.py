"""
Analyst Module — orchestrates Volume Profile analysis and spread construction.

Consumes the output from the scanner and produces fully specified
trade recommendations (buy/sell strikes, expiry, P&L, risk/reward).

Pipeline
--------
1. Receive candidate list from scanner.
2. For each candidate:
   a. Fetch 60-day daily candles.
   b. Check ADV (skip dead stocks).
   c. Build Volume Profile → POC, Value Area, HVN walls.
   d. Map the appropriate wall (support/resistance) to trend.
   e. Fetch option chain → filter by nearest monthly expiry.
   f. Select short + long strikes.
   g. Fetch option premiums → compute spread P&L.
3. Return list of trade recommendations.

Usage:
    from analyst.analyst import analyze_candidates

    recommendations = analyze_candidates(scanner_candidates, kite)
"""

import logging
import random
import time
from typing import Any

import config
from analyst.volume_profile import calculate_volume_profile, find_hvn_walls
from analyst.strike_selector import (
    compute_spread_pnl,
    find_nearest_monthly_expiry,
    select_strikes,
)
from core.instrument_master import build_nse_token_map, get_nfo_option_chain
from core.kite_client import KiteClient

logger = logging.getLogger(__name__)


def analyze_candidates(
    candidates: list[dict[str, Any]],
    kite: KiteClient,
    nse_token_map: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """
    Analyze scanner candidates and produce trade recommendations.

    Parameters
    ----------
    candidates : list[dict]
        Output of scanner.run_scan() — each dict has:
        symbol, score, method, trend, ema_50, spot, current_iv.
    kite : KiteClient
        Authenticated Kite client.
    nse_token_map : dict or None
        Pre-built {symbol → instrument_token} map. If None, fetched fresh.

    Returns
    -------
    list[dict]
        Each dict is a fully specified trade recommendation.
        Empty list if no viable trades are found.
    """
    logger.info("═══ Starting Analyst Run — %d candidates ═══", len(candidates))

    if nse_token_map is None:
        time.sleep(random.uniform(0.3, 0.8))
        nse_token_map = build_nse_token_map(kite)

    recommendations: list[dict[str, Any]] = []

    for i, candidate in enumerate(candidates, 1):
        symbol = candidate["symbol"]
        spot = candidate["spot"]
        trend = candidate["trend"]

        logger.info(
            "[%d/%d] Analyzing %s (trend=%s, spot=%.2f) …",
            i, len(candidates), symbol, trend, spot,
        )

        try:
            result = _analyze_single(candidate, kite, nse_token_map)
            if result:
                recommendations.append(result)
                logger.info("  ✓ Trade recommendation generated for %s.", symbol)
            else:
                logger.info("  ✗ No viable trade for %s.", symbol)
        except Exception as exc:
            logger.error("  ✗ Error analyzing %s: %s", symbol, exc)

    logger.info(
        "═══ Analyst complete: %d recommendations from %d candidates ═══",
        len(recommendations), len(candidates),
    )
    return recommendations


def _analyze_single(
    candidate: dict[str, Any],
    kite: KiteClient,
    nse_token_map: dict[str, int],
) -> dict[str, Any] | None:
    """Analyze a single candidate through the full VP → strike pipeline."""
    symbol = candidate["symbol"]
    spot = candidate["spot"]
    trend = candidate["trend"]

    nse_token = nse_token_map.get(symbol)
    if not nse_token:
        logger.warning("  No NSE token for %s — skipping.", symbol)
        return None

    # ── Step 1: Fetch candles ──
    time.sleep(random.uniform(0.3, 0.8))
    candles = kite.historical_data(nse_token, "day", config.VP_LOOKBACK_DAYS + 30)
    # Fetch extra days to ensure we have at least VP_LOOKBACK_DAYS valid candles

    if len(candles) < 30:
        logger.warning("  Only %d candles for %s — skipping.", len(candles), symbol)
        return None

    # ── Step 2: Volume Profile ──
    profile = calculate_volume_profile(candles)
    if profile is None:
        return None

    # ── Step 3: Find HVN walls ──
    walls = find_hvn_walls(profile, spot)
    logger.info(
        "  VP: POC=%.2f | VA=[%.2f, %.2f] | Support=%.2f | Resistance=%s",
        profile["poc"],
        profile["va_low"], profile["va_high"],
        walls["support_wall"] or 0,
        walls["resistance_wall"] or "N/A",
    )

    # Determine which wall to use based on trend
    if trend == "Bullish":
        wall_price = walls["support_wall"]
        if wall_price is None:
            logger.info("  No support wall found for Bullish %s.", symbol)
            return None
    elif trend == "Bearish":
        wall_price = walls["resistance_wall"]
        if wall_price is None:
            logger.info("  No resistance wall found for Bearish %s.", symbol)
            return None
    else:
        logger.warning("  Unknown trend '%s' for %s.", trend, symbol)
        return None

    # ── Step 4: Fetch option chain ──
    time.sleep(random.uniform(0.3, 0.8))
    option_chain = get_nfo_option_chain(kite, symbol)
    if not option_chain:
        logger.warning("  Empty option chain for %s.", symbol)
        return None

    # ── Step 5: Select strikes ──
    strike_result = select_strikes(
        wall_price=wall_price,
        spot=spot,
        trend=trend,
        option_chain=option_chain,
    )
    if strike_result is None:
        return None

    # ── Step 6: Fetch option premiums ──
    short_sym = f"NFO:{strike_result['short_instrument']['tradingsymbol']}"
    long_sym = f"NFO:{strike_result['long_instrument']['tradingsymbol']}"

    time.sleep(random.uniform(0.3, 0.8))
    try:
        quotes = kite.ltp([short_sym, long_sym])
    except Exception as exc:
        logger.warning("  Premium fetch failed: %s", exc)
        return None

    short_premium = quotes.get(short_sym, {}).get("last_price", 0)
    long_premium = quotes.get(long_sym, {}).get("last_price", 0)

    if short_premium <= 0:
        logger.warning("  Short premium is zero for %s — skipping.", symbol)
        return None

    # ── Step 7: Compute spread P&L ──
    spread_width = abs(strike_result["short_strike"] - strike_result["long_strike"])
    pnl = compute_spread_pnl(
        short_premium=short_premium,
        long_premium=long_premium,
        lot_size=strike_result["lot_size"],
        spread_width=spread_width,
    )

    # ── Assemble recommendation ──
    return {
        "symbol": symbol,
        "trend": trend,
        "spot": spot,
        "score": candidate.get("score"),
        "score_method": candidate.get("method"),
        "current_iv": candidate.get("current_iv"),
        # Volume Profile
        "poc": profile["poc"],
        "va_high": profile["va_high"],
        "va_low": profile["va_low"],
        "adv": profile["adv"],
        "support_wall": walls["support_wall"],
        "resistance_wall": walls["resistance_wall"],
        # Spread details
        "spread": {
            "type": strike_result["spread_type"],
            "short_strike": strike_result["short_strike"],
            "long_strike": strike_result["long_strike"],
            "short_symbol": strike_result["short_instrument"]["tradingsymbol"],
            "long_symbol": strike_result["long_instrument"]["tradingsymbol"],
            "expiry": strike_result["expiry"],
            "lot_size": strike_result["lot_size"],
            "short_premium": short_premium,
            "long_premium": long_premium,
            **pnl,
        },
    }
