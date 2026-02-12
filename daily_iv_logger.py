"""
Daily IV Logger — Cron job entry point.

Runs every trading day at 15:25 IST (configurable in config.py).
For each F&O stock:
    1. Find the nearest ATM option (CE + PE).
    2. Compute IV from the ATM option price via Black-Scholes.
    3. Compute 20-day Historical Volatility.
    4. Persist both to the `iv_history` table.

Run modes
---------
    python daily_iv_logger.py --once      # Run once and exit (for testing)
    python daily_iv_logger.py             # Start the scheduler loop

Dependencies:
    Requires KITE_ACCESS_TOKEN to be set (either env var or config.py).
"""

import argparse
import logging
import math
import random
import time
from datetime import datetime

import schedule

import config
from core.iv_calculator import implied_volatility
from core.hv_calculator import calculate_hv
from core.kite_client import KiteClient
from db.connection import get_connection
from db.schema import initialise_database

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(name)s  —  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("iv_logger")


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _get_fno_symbols(kite: KiteClient) -> list[dict]:
    """
    Return a unique list of F&O equity stock symbols from
    the NFO instrument master.

    Filters for equity futures (FUT segment) to get the
    canonical list of stocks with F&O contracts.
    """
    instruments = kite.instruments("NFO")
    seen = set()
    fno_stocks = []

    for inst in instruments:
        name = inst.get("name", "")
        segment = inst.get("segment", "")
        instrument_type = inst.get("instrument_type", "")

        # Keep only equity futures to derive unique underlying names
        if segment == "NFO-FUT" and instrument_type == "FUT" and name not in seen:
            seen.add(name)
            fno_stocks.append(
                {
                    "symbol": name,
                    "exchange_token": inst["exchange_token"],
                    "instrument_token": inst["instrument_token"],
                }
            )

    logger.info("Found %d unique F&O stocks.", len(fno_stocks))
    return fno_stocks


def _find_atm_option(
    kite: KiteClient,
    stock_symbol: str,
    spot_price: float,
    option_type: str = "CE",
) -> dict | None:
    """
    Find the nearest ATM option instrument for a given underlying.

    Fetches all NFO instruments, filters by the underlying name and
    option type, and returns the one whose strike is closest to spot.

    Returns the instrument dict or None if nothing found.
    """
    instruments = kite.instruments("NFO")
    options = [
        inst for inst in instruments
        if inst.get("name") == stock_symbol
        and inst.get("instrument_type") == option_type
    ]

    if not options:
        return None

    # Closest strike to spot price
    return min(options, key=lambda o: abs(o["strike"] - spot_price))


def _days_to_expiry(expiry_date) -> float:
    """Calendar days until expiry, as a fraction of a year."""
    if isinstance(expiry_date, str):
        expiry_dt = datetime.fromisoformat(expiry_date)
    else:
        expiry_dt = datetime.combine(expiry_date, datetime.min.time())

    delta = (expiry_dt - datetime.now()).days
    return max(delta, 1) / 365.0


def _save_iv_record(
    symbol: str,
    atm_iv: float,
    hv_20: float | None,
) -> None:
    """Insert a row into iv_history, keyed by date (not full timestamp)."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO iv_history
                (stock_symbol, timestamp, atm_iv, hv_20_day)
            VALUES (?, ?, ?, ?)
            """,
            (symbol, today_str, atm_iv, hv_20),
        )
    logger.info("  ✓ Saved IV=%.4f  HV=%.4f  for %s", atm_iv, hv_20 or 0, symbol)


def _get_already_logged_today() -> set[str]:
    """Return the set of stock symbols that already have a record for today."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT stock_symbol FROM iv_history WHERE timestamp = ?",
            (today_str,),
        ).fetchall()
    return {row[0] for row in rows}


# ──────────────────────────────────────────────
# Main job
# ──────────────────────────────────────────────

def run_iv_snapshot() -> None:
    """
    Core logic: iterate F&O stocks, compute IV & HV, persist.
    """
    logger.info("═══ Starting IV snapshot run ═══")
    kite = KiteClient()

    # ── Preflight: verify access token is valid ──
    token_valid = False
    if config.KITE_ACCESS_TOKEN:
        try:
            kite.margins()  # lightweight call to validate session
            token_valid = True
            logger.info("✓ Existing access token is valid.")
        except Exception as err:
            logger.warning("Existing token expired/invalid: %s", err)

    if not token_valid:
        # ── Inline login flow ──────────────────────
        # Step 1: Print login URL for user
        login_url = kite.get_login_url()
        print()
        print("┌─────────────────────────────────────────────────────────┐")
        print("│          IV-Sniper — Kite Connect Login                 │")
        print("├─────────────────────────────────────────────────────────┤")
        print("│  1. Open the URL below in your browser                 │")
        print("│  2. Login with your Zerodha credentials                │")
        print("│  3. After redirect, copy the 'request_token' from      │")
        print("│     the URL bar (after ?request_token=XXXXX...)        │")
        print("│  4. Paste it below                                     │")
        print("└─────────────────────────────────────────────────────────┘")
        print()
        print(f"  Login URL: {login_url}")
        print()

        request_token = input("  Paste your request_token here: ").strip()
        if not request_token:
            logger.error("No request_token provided. Aborting.")
            return

        # Step 2: Exchange request_token → access_token
        try:
            session_data = kite.generate_session(request_token)
            access_token = session_data["access_token"]
            logger.info("✓ Session generated successfully.")
        except Exception as exc:
            logger.error(
                "Session generation failed!\n"
                "  Error Type : %s\n"
                "  Error Code : %s\n"
                "  Message    : %s",
                type(exc).__name__,
                getattr(exc, "code", "N/A"),
                exc,
            )
            return

        # Step 3: Persist to .env so next run auto-connects
        try:
            from dotenv import set_key
            from pathlib import Path
            env_path = Path(__file__).resolve().parent / ".env"
            set_key(str(env_path), "KITE_ACCESS_TOKEN", access_token)
            logger.info("✓ Access token saved to .env")
        except Exception as save_err:
            logger.warning("Could not save token to .env: %s", save_err)

        # Step 4: Verify the new token works
        try:
            kite.margins()
            logger.info("✓ New access token verified successfully.")
        except Exception as verify_err:
            logger.error("New token verification failed: %s", verify_err)
            return

    # ── Resume support: skip already-processed stocks ──
    already_done = _get_already_logged_today()
    if already_done:
        logger.info(
            "✓ Found %d stocks already logged today — will skip them.",
            len(already_done),
        )

    fno_stocks = _get_fno_symbols(kite)

    # ── Pre-fetch NSE instrument list once (not per-stock!) ──
    logger.info("Fetching NSE instrument master (one-time)…")
    time.sleep(random.uniform(0.3, 0.8))
    nse_instruments = kite.instruments("NSE")
    nse_token_map = {}
    for inst in nse_instruments:
        if inst["segment"] == "NSE":
            nse_token_map[inst["tradingsymbol"]] = inst["instrument_token"]
    logger.info("✓ NSE instrument map built (%d symbols).", len(nse_token_map))

    success_count = 0
    skip_count = 0
    resume_skip = 0

    for i, stock in enumerate(fno_stocks, 1):
        symbol = stock["symbol"]

        # ── Skip if already done today ──
        if symbol in already_done:
            resume_skip += 1
            continue

        logger.info("[%d/%d] Processing %s …", i, len(fno_stocks), symbol)

        try:
            # 1. Get spot price
            time.sleep(random.uniform(0.3, 0.8))
            ltp_data = kite.ltp([f"NSE:{symbol}"])
            spot = ltp_data.get(f"NSE:{symbol}", {}).get("last_price")
            if not spot:
                logger.warning("  ✗ No LTP for %s — skipping.", symbol)
                skip_count += 1
                continue

            # 2. Find ATM CE option
            atm_option = _find_atm_option(kite, symbol, spot, "CE")
            if not atm_option:
                logger.warning("  ✗ No ATM option found for %s — skipping.", symbol)
                skip_count += 1
                continue

            # 3. Get option market price
            time.sleep(random.uniform(0.3, 0.8))
            opt_key = f"NFO:{atm_option['tradingsymbol']}"
            opt_quote = kite.ltp([opt_key])
            opt_price = opt_quote.get(opt_key, {}).get("last_price")
            if not opt_price or opt_price <= 0:
                logger.warning("  ✗ No valid option price for %s — skipping.", symbol)
                skip_count += 1
                continue

            # 4. Compute IV
            tte = _days_to_expiry(atm_option["expiry"])
            iv = implied_volatility(
                option_price=opt_price,
                spot=spot,
                strike=atm_option["strike"],
                time_to_expiry_years=tte,
                option_type="CE",
            )
            if iv is None:
                logger.warning("  ✗ IV did not converge for %s — skipping.", symbol)
                skip_count += 1
                continue

            # 5. Compute 20-day HV
            hv_20 = None
            try:
                nse_token = nse_token_map.get(symbol)
                if nse_token:
                    time.sleep(random.uniform(0.3, 0.8))
                    candles = kite.historical_data(nse_token, "day", 365)
                    hv_20 = calculate_hv(candles)
            except Exception as hv_err:
                logger.warning("  ⚠ HV calc failed for %s: %s", symbol, hv_err)

            # 6. Persist
            _save_iv_record(symbol, iv, hv_20)
            success_count += 1

        except Exception as exc:
            err_msg = str(exc)
            # ── Handle rate-limit: back off instead of skipping ──
            if "Too many requests" in err_msg or "Rate limit" in err_msg:
                wait = random.uniform(8, 20)
                logger.warning(
                    "  ⏳ Rate limited on %s — backing off %.1fs …",
                    symbol, wait,
                )
                time.sleep(wait)
                # Not counted as skip — will be retried on next re-run
            else:
                logger.error("  ✗ Error processing %s: %s", symbol, exc)
                skip_count += 1

        # Random delay between stocks to stay under rate limits
        time.sleep(random.uniform(0.5, 1.2))

    logger.info(
        "═══ Snapshot complete: %d saved, %d skipped, %d already done ═══",
        success_count,
        skip_count,
        resume_skip,
    )


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="IV-Sniper Daily IV Logger")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run the IV snapshot once and exit (useful for testing).",
    )
    args = parser.parse_args()

    # Ensure DB tables exist
    initialise_database()

    if args.once:
        logger.info("Running single IV snapshot (--once mode).")
        run_iv_snapshot()
        return

    # Schedule mode — run daily at configured time
    logger.info(
        "Scheduler started. IV snapshot scheduled at %s IST daily.",
        config.IV_LOG_TIME,
    )
    schedule.every().day.at(config.IV_LOG_TIME).do(run_iv_snapshot)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
