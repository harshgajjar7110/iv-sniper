"""
run_executor.py — Main Entry Point for IV-Sniper Execution Engine.

Runs the full pipeline:
1. Scanner: Find high-IV opportunities.
2. Analyst: Generate trade plans (Volume Profile + Spread).
3. Executor: Validate risks and execute trades (Paper/Live).

Usage:
    python run_executor.py
    python run_executor.py --top 5 --min-score 40
"""

import argparse
import logging
import sys
import time

from core.kite_client import KiteClient
from scanner.scanner import run_scan
from analyst.analyst import analyze_candidates
from executor.executor import execute_trades
import config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("IV-Sniper")


def main():
    parser = argparse.ArgumentParser(description="IV-Sniper Auto-Trader")
    parser.add_argument("--top", type=int, default=3, help="Max candidates to scan")
    parser.add_argument("--min-score", type=float, default=50.0, help="Min IVP/HV score")
    args = parser.parse_args()

    # 1. Auth
    try:
        kite = KiteClient()
        kite.margins() # Validate token
        logger.info("✓ Kite session active.")
    except Exception as e:
        logger.error(f"Kite session failed: {e}")
        print("Run auth_login.py to refresh token.")
        sys.exit(1)

    mode = "PAPER" if config.PAPER_TRADE_MODE else "LIVE"
    logger.info(f"Starting IV-Sniper in {mode} MODE")
    
    # 2. Scanner
    candidates = run_scan(kite, max_candidates=args.top, min_score=args.min_score)
    if not candidates:
        logger.info("No candidates found.")
        return

    # 3. Analyst
    recommendations = analyze_candidates(candidates, kite)
    if not recommendations:
        logger.info("No valid trade setups found.")
        return

    # 4. Executor
    logger.info(f"Attempting to execute {len(recommendations)} trades...")
    executed = execute_trades(recommendations, kite)
    
    logger.info(f"Execution complete. Trades placed: {executed}")
    if executed > 0:
        print(f"\n[✔] {executed} trades executed in {mode} mode.")
        print("Run 'python scripts/view_trades.py' to see details.")


if __name__ == "__main__":
    main()
