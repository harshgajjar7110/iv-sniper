"""
Watchdog Job — Cyclical monitoring of open positions.

Usage:
    python watchdog_job.py          # Run as loop (every 5 mins)
    python watchdog_job.py --once   # Run once and exit
"""

import argparse
import logging
import time
import schedule
import sys

from core.kite_client import KiteClient
from watchdog.monitor import run_watchdog
import config

# Config logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] watchdog: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("IV-Sniper-Watchdog")


def job():
    """Wrapper for the monitoring task."""
    try:
        logger.info("Starting monitoring cycle...")
        kite = KiteClient() # New session each time? Or reuse?
        # Reuse if possible to avoid login spam?
        # But token might expire. KiteClient handles session?
        # KiteClient reads from .env. It's lightweight.
        # But `kite.margins()` call inside validates token.
        
        # Check token validity
        try:
            kite.margins()
        except Exception:
            logger.error("Token invalid. Aborting cycle.")
            return

        run_watchdog(kite)
        logger.info("Cycle complete.")
        
    except Exception as e:
        logger.error(f"Job failed: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    logger.info("Watchdog started.")
    
    if args.once:
        job()
        return

    # Schedule every 5 minutes
    schedule.every(5).minutes.do(job)
    
    logger.info("Scheduled to run every 5 minutes. Press Ctrl+C to stop.")
    
    # Run immediately once
    job()
    
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Watchdog stopped by user.")
        sys.exit(0)
