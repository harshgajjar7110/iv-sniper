"""
Scanner CLI — Run the IV/IVP scanner and print candidates.

Usage:
    python run_scanner.py                    # Default: top 5, min score 50%
    python run_scanner.py --top 3            # Return top 3
    python run_scanner.py --min-score 60     # Min IVP/HV Rank of 60%

Output:
    A formatted table of qualified stocks with their IV score and trend.
"""

import argparse
import logging

from db.schema import initialise_database
from scanner.scanner import run_scan

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(name)s  —  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("run_scanner")


def _print_results(candidates: list[dict]) -> None:
    """Pretty-print the scan results as a formatted table."""
    if not candidates:
        print("\n  ⚠  No stocks passed the filter. Try lowering --min-score.\n")
        return

    # Header
    print()
    print("┌─────┬──────────────┬─────────┬────────┬──────────┬────────────┬────────────┐")
    print("│  #  │ Symbol       │ Method  │ Score  │  Trend   │    Spot    │   EMA-50   │")
    print("├─────┼──────────────┼─────────┼────────┼──────────┼────────────┼────────────┤")

    for i, c in enumerate(candidates, 1):
        ema_str = f"{c['ema_50']:.2f}" if c["ema_50"] else "N/A"
        print(
            f"│ {i:>2}  │ {c['symbol']:<12} │ {c['method']:<7} │ {c['score']:>5.1f}% │"
            f" {c['trend']:<8} │ {c['spot']:>10.2f} │ {ema_str:>10} │"
        )

    print("└─────┴──────────────┴─────────┴────────┴──────────┴────────────┴────────────┘")
    print(f"\n  Total candidates: {len(candidates)}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="IV-Sniper Scanner — find high IV/IVP stocks"
    )
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="Maximum number of candidates to return (default: 5).",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=50.0,
        help="Minimum IVP or HV Rank percentage to qualify (default: 50).",
    )
    args = parser.parse_args()

    # Ensure DB exists
    initialise_database()

    logger.info(
        "Running scanner: top=%d, min_score=%.0f%%",
        args.top,
        args.min_score,
    )

    candidates = run_scan(
        max_candidates=args.top,
        min_score=args.min_score,
    )

    _print_results(candidates)


if __name__ == "__main__":
    main()
