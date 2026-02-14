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
4. Save ALL results to scan_history table in database.

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

import json
import logging
import random
import time
import threading
import uuid
from datetime import datetime
from typing import Any, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

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

# Rate limiting configuration (loaded from config)
SCANNER_RATE_LIMIT_ENABLED = getattr(config, 'SCANNER_RATE_LIMIT_ENABLED', True)
SCANNER_MIN_DELAY = getattr(config, 'SCANNER_MIN_DELAY_SECONDS', 1.0)
SCANNER_MAX_DELAY = getattr(config, 'SCANNER_MAX_DELAY_SECONDS', 2.0)
SCANNER_THREAD_POOL_SIZE = getattr(config, 'SCANNER_THREAD_POOL_SIZE', 3)


def _apply_rate_limit_delay() -> None:
    """Apply a random delay to honor rate limits on the server side."""
    if SCANNER_RATE_LIMIT_ENABLED:
        delay = random.uniform(SCANNER_MIN_DELAY, SCANNER_MAX_DELAY)
        logger.debug("Rate limit delay: %.2f seconds", delay)
        time.sleep(delay)


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
    save_to_db: bool = True,
    progress_callback: Callable[[int, int, str, int], None] | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
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
    save_to_db : bool
        Whether to save results to database (default: True).
    progress_callback : Callable or None
        Optional callback for progress updates. Called with:
        - current: int — number of stocks processed
        - total: int — total stocks to process
        - message: str — current status message
        - qualified: int — number of stocks that qualified

    Returns
    -------
    tuple[list[dict], str | None]
        First element: list of candidate dictionaries.
        Second element: scan_id if saved to DB, None otherwise.
        
        Each candidate dict contains:
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
    scan_start_time = datetime.now()
    total_scanned = 0
    scan_id = str(uuid.uuid4()) if save_to_db else None
    scan_time = scan_start_time.isoformat()

    if kite is None:
        kite = KiteClient()

    if not _validate_token(kite):
        logger.error("Cannot run scanner — invalid token.")
        if progress_callback:
            progress_callback(0, 0, "Error: Invalid token", 0)
        return [], None

    # ── Step 1: Fetch instrument masters ──
    if progress_callback:
        progress_callback(0, 0, "Fetching F&O instrument list...", 0)
    
    fno_stocks = get_fno_stocks(kite)
    _apply_rate_limit_delay()
    nse_token_map = build_nse_token_map(kite)
    _apply_rate_limit_delay()

    scored: list[dict[str, Any]] = []
    all_results: list[dict[str, Any]] = []  # Track ALL stocks for scan_history
    
    # Filter out index symbols
    stock_list = [
        stock for stock in fno_stocks
        if stock["symbol"] not in (
            "NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"
        )
    ]
    total_scanned = len(stock_list)
    
    logger.info(
        "Scanning %d F&O stocks (min score: %.0f%%) with rate limiting (%.1f-%.1fs delay)...",
        total_scanned,
        min_score,
        SCANNER_MIN_DELAY,
        SCANNER_MAX_DELAY,
    )

    # Thread-safe progress tracking
    progress_lock = threading.Lock()
    processed_count = 0
    qualified_count = 0
    results_lock = threading.Lock()

    def update_progress(symbol: str, qualified: bool = False) -> None:
        """Update progress counter and call callback if provided."""
        nonlocal processed_count, qualified_count
        if progress_callback:
            with progress_lock:
                processed_count += 1
                if qualified:
                    qualified_count += 1
                progress_callback(
                    processed_count,
                    total_scanned,
                    f"Processing {symbol}...",
                    qualified_count
                )

    # Parallel processing with reduced workers for conservative rate limits
    # Using reduced thread pool size to avoid overwhelming the API
    with ThreadPoolExecutor(max_workers=SCANNER_THREAD_POOL_SIZE) as executor:
        futures = {
            executor.submit(
                _process_stock, kite, stock["symbol"], nse_token_map, min_score
            ): stock["symbol"]
            for stock in stock_list
        }

        for future in as_completed(futures):
            symbol = futures[future]
            try:
                result = future.result()
                with results_lock:
                    if result:
                        # Track all results for scan_history
                        all_results.append(result)
                        if result.get("qualified", False):
                            scored.append(result)
                            update_progress(symbol, qualified=True)
                        else:
                            update_progress(symbol, qualified=False)
                    else:
                        # Still track stocks that couldn't be processed
                        all_results.append({
                            "symbol": symbol,
                            "score": None,
                            "method": None,
                            "trend": None,
                            "ema_50": None,
                            "spot": None,
                            "atm_iv": None,
                            "hv_20": None,
                            "qualified": False,
                        })
                        update_progress(symbol, qualified=False)
            except Exception as exc:
                logger.error("Error processing %s: %s", symbol, exc)
                with results_lock:
                    all_results.append({
                        "symbol": symbol,
                        "score": None,
                        "method": None,
                        "trend": None,
                        "ema_50": None,
                        "spot": None,
                        "atm_iv": None,
                        "hv_20": None,
                        "qualified": False,
                    })
                update_progress(symbol, qualified=False)

    # ── Step 3: Sort and truncate ──
    if progress_callback:
        progress_callback(total_scanned, total_scanned, "Sorting results...", len(scored))
    
    scored.sort(key=lambda c: c.get("score", 0) or 0, reverse=True)
    top = scored[:max_candidates]

    # ── Step 4: Save ALL results to scan_history database ──
    if save_to_db and scan_id:
        try:
            from db.repositories import scan_history_repo
            
            # Prepare all results with scan metadata
            history_records = []
            for result in all_results:
                history_records.append({
                    "scan_id": scan_id,
                    "scan_time": scan_time,
                    "symbol": result["symbol"],
                    "score": result.get("score"),
                    "method": result.get("method"),
                    "trend": result.get("trend"),
                    "ema_50": result.get("ema_50"),
                    "spot_price": result.get("spot"),
                    "atm_iv": result.get("atm_iv") or result.get("current_iv"),
                    "hv_20": result.get("hv_20"),
                    "qualified": result.get("qualified", False),
                    "min_score_threshold": min_score,
                })
            
            # Bulk insert all scan results
            scan_history_repo.bulk_insert_scan_results(history_records)
            logger.info(
                "Saved %d scan results to scan_history with ID: %s",
                len(history_records), scan_id
            )
            
            # Also save qualified candidates to scan_results (for backward compatibility)
            if top:
                from db.scan_store import save_scan_result
                save_scan_result(
                    candidates=top,
                    min_ivp=min_score,
                    min_hv_rank=min_score,
                    total_scanned=total_scanned,
                )
                
        except Exception as e:
            logger.warning("Failed to save scan results to database: %s", e)

    scan_duration = (datetime.now() - scan_start_time).total_seconds()
    logger.info(
        "═══ Scan complete: %d qualified, returning top %d (scanned %d stocks in %.1fs) ═══",
        len(scored),
        len(top),
        total_scanned,
        scan_duration,
    )
    
    if progress_callback:
        progress_callback(
            total_scanned, 
            total_scanned, 
            f"Scan complete! {len(scored)} qualified, {len(top)} returned", 
            len(scored)
        )

    return top, scan_id


def _process_stock(
    kite: KiteClient,
    symbol: str,
    nse_token_map: dict[str, int],
    min_score: float,
) -> dict[str, Any] | None:
    """Helper to process a single stock (runs in thread).
    
    Returns a dict with all scan data including qualified status.
    Returns None only if the stock cannot be processed at all.
    """
    nse_token = nse_token_map.get(symbol)

    # ── Step 2a: IV Score ──
    # Random sleep to prevent rigid thundering herd and honor rate limits
    _apply_rate_limit_delay()
    
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
    current_iv = iv_result.get("current_iv")
    hv_20 = iv_result.get("hv_20")  # Get HV from iv_result

    # ── Step 2c: Get spot price ──
    _apply_rate_limit_delay()
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
    _apply_rate_limit_delay()
    trend_data = {"trend": "Unknown", "ema_50": None, "spot": spot}
    if nse_token:
        try:
            # We need 120 days history for EMA-50
            # This is the most expensive call.
            candles = kite.historical_data(nse_token, "day", 120)
            trend_data = detect_trend(candles, spot)
        except Exception as exc:
            logger.warning("Trend detection failed for %s: %s", symbol, exc)

    # Determine if qualified
    qualified = score >= min_score
    
    result = {
        "symbol": symbol,
        "score": score,
        "method": method,
        "trend": trend_data["trend"],
        "ema_50": trend_data.get("ema_50"),
        "spot": spot,
        "current_iv": current_iv,
        "atm_iv": current_iv,  # Include both for compatibility
        "hv_20": hv_20,
        "qualified": qualified,
    }
    
    if qualified:
        logger.info(
            "  ✓ %s — %s = %.1f%% | Trend: %s",
            symbol, method, score, trend_data["trend"]
        )
    else:
        logger.debug(
            "  ✗ %s — %s = %.1f%% (below threshold %.0f%%)",
            symbol, method, score, min_score
        )
    
    return result
