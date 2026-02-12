"""
run_analyst.py — CLI entry point for the Analyst module.

Runs the full pipeline: Scanner → Volume Profile → Strike Selection → Spread.

Usage:
    python run_analyst.py                          # Default: top 3, min score 50
    python run_analyst.py --top 5 --min-score 30   # More candidates, lower bar
"""

import argparse
import logging
import sys

from analyst.analyst import analyze_candidates
from core.kite_client import KiteClient
from scanner.scanner import run_scan

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-25s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_analyst")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="IV-Sniper Analyst — Volume Profile & Spread Builder"
    )
    parser.add_argument(
        "--top", type=int, default=3,
        help="Max candidates to analyze (default: 3)",
    )
    parser.add_argument(
        "--min-score", type=float, default=50.0,
        help="Minimum IVP / HV Rank to qualify (default: 50)",
    )
    args = parser.parse_args()

    # ── Authenticate ──
    kite = KiteClient()
    try:
        kite.margins()
        logger.info("✓ Kite session active.")
    except Exception as exc:
        logger.error("✗ Kite session invalid: %s", exc)
        print("\nRun auth_login.py first to get a valid access token.")
        sys.exit(1)

    # ── Step 1: Scanner ──
    print("\n" + "═" * 60)
    print("  STEP 1 — SCANNING FOR HIGH-IV CANDIDATES")
    print("═" * 60)

    candidates = run_scan(
        kite=kite,
        max_candidates=args.top,
        min_score=args.min_score,
    )

    if not candidates:
        print("\n  No candidates found. Try lowering --min-score.\n")
        return

    print(f"\n  Found {len(candidates)} candidates:\n")
    for c in candidates:
        print(
            f"    {c['symbol']:>15s}  │  {c['method']:>7s} = {c['score']:5.1f}%"
            f"  │  Trend: {c['trend']:>7s}  │  Spot: ₹{c['spot']:>10,.2f}"
        )

    # ── Step 2: Analyst ──
    print("\n" + "═" * 60)
    print("  STEP 2 — VOLUME PROFILE & SPREAD ANALYSIS")
    print("═" * 60 + "\n")

    recommendations = analyze_candidates(candidates, kite)

    if not recommendations:
        print("\n  No viable trades found after analysis.\n")
        return

    # ── Print results ──
    print("\n" + "═" * 70)
    print("  TRADE RECOMMENDATIONS")
    print("═" * 70)

    for rec in recommendations:
        sp = rec["spread"]
        print(f"""
┌──────────────────────────────────────────────────────────────────┐
│  {rec['symbol']:<15s}  │  {rec['trend']:>7s}  │  Score: {rec['score']:.1f}%  ({rec['score_method']})
├──────────────────────────────────────────────────────────────────┤
│  Spot: ₹{rec['spot']:>10,.2f}  │  IV: {(rec.get('current_iv') or 0)*100:.1f}%  │  ADV: {rec['adv']:,.0f}
│  POC:  ₹{rec['poc']:>10,.2f}  │  VA: [₹{rec['va_low']:,.2f} — ₹{rec['va_high']:,.2f}]
│  Support Wall:    ₹{rec['support_wall'] or 0:>10,.2f}
│  Resistance Wall: ₹{rec.get('resistance_wall') or 0:>10,.2f}
├──────────────────────────────────────────────────────────────────┤
│  Spread Type: {sp['type']}
│  SELL: {sp['short_symbol']:<25s}  @ ₹{sp['short_strike']:>10,.2f}  (₹{sp['short_premium']:>8,.2f})
│  BUY:  {sp['long_symbol']:<25s}  @ ₹{sp['long_strike']:>10,.2f}  (₹{sp['long_premium']:>8,.2f})
│  Expiry: {sp['expiry']}  │  Lot: {sp['lot_size']}
├──────────────────────────────────────────────────────────────────┤
│  Net Credit:  ₹{sp['net_credit']:>10,.2f}  │  Max Profit: ₹{sp['max_profit']:>10,.2f}
│  Max Loss:    ₹{sp['max_loss']:>10,.2f}  │  RR Ratio:   {sp['risk_reward']:.3f}
│  SL at:       ₹{sp['sl_premium']:>10,.2f}  ({sp['sl_pct']:.0f}% of credit)
│  Target at:   ₹{sp['target_premium']:>10,.2f}  ({sp['target_pct']:.0f}% of credit)
└──────────────────────────────────────────────────────────────────┘""")

    print()


if __name__ == "__main__":
    main()
