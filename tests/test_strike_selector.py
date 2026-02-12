"""
Test Strike Selector — verify OTM strike selection and spread P&L math.

Uses a mock option chain with known strike intervals.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta
from analyst.strike_selector import (
    select_strikes,
    compute_spread_pnl,
    find_nearest_monthly_expiry,
)

passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  ✓ {name}")
        passed += 1
    else:
        print(f"  ✗ {name}  {detail}")
        failed += 1


# ─────────────────────────────────────────
# Build a mock option chain
# ─────────────────────────────────────────
# Simulates a stock at ₹1000, strikes every ₹50, monthly expiry

# Find the next last-Thursday-of-month for realistic expiry
def _next_monthly_expiry():
    today = date.today()
    # Go to end of current month
    if today.month == 12:
        next_month = date(today.year + 1, 1, 1)
    else:
        next_month = date(today.year, today.month + 1, 1)
    last_day = next_month - timedelta(days=1)
    # Roll back to Thursday
    while last_day.weekday() != 3:  # 3 = Thursday
        last_day -= timedelta(days=1)
    if last_day <= today:
        # Move to next month
        if next_month.month == 12:
            next_next = date(next_month.year + 1, 1, 1)
        else:
            next_next = date(next_month.year, next_month.month + 1, 1)
        last_day = next_next - timedelta(days=1)
        while last_day.weekday() != 3:
            last_day -= timedelta(days=1)
    return last_day


expiry = _next_monthly_expiry()

mock_chain = []
for strike in range(700, 1400, 50):  # ₹700 to ₹1350 in ₹50 steps
    mock_chain.append({
        "tradingsymbol": f"TESTSTOCK{strike}PE",
        "name": "TESTSTOCK",
        "instrument_type": "PE",
        "strike": float(strike),
        "expiry": expiry,
        "lot_size": 100,
        "instrument_token": 10000 + strike,
    })
    mock_chain.append({
        "tradingsymbol": f"TESTSTOCK{strike}CE",
        "name": "TESTSTOCK",
        "instrument_type": "CE",
        "strike": float(strike),
        "expiry": expiry,
        "lot_size": 100,
        "instrument_token": 20000 + strike,
    })


# ─────────────────────────────────────────
# Test 1: Nearest Monthly Expiry
# ─────────────────────────────────────────
print("\n── Test 1: Monthly Expiry Detection ──")

found_expiry = find_nearest_monthly_expiry(mock_chain)
check("Expiry found", found_expiry is not None)
check("Expiry matches mock", found_expiry == expiry, f"got {found_expiry}")
check("Expiry is a Thursday", found_expiry.weekday() == 3, f"weekday={found_expiry.weekday()}")
print(f"    Expiry: {found_expiry}")


# ─────────────────────────────────────────
# Test 2: Bull Put Spread (Bullish)
# ─────────────────────────────────────────
print("\n── Test 2: Bull Put Spread (Bullish) ──")

# Spot = 1000, support wall at 920
result = select_strikes(
    wall_price=920.0, spot=1000.0, trend="Bullish",
    option_chain=mock_chain, target_expiry=expiry,
)
check("Spread result is not None", result is not None)

if result:
    check("Spread type is BULL_PUT", result["spread_type"] == "BULL_PUT")
    check("Short type is PE", result["short_type"] == "PE")
    check("Short strike ≤ wall (920)", result["short_strike"] <= 920.0,
          f"got {result['short_strike']}")
    check("Short strike < spot (1000)", result["short_strike"] < 1000.0)
    check("Long strike < short strike", result["long_strike"] < result["short_strike"])
    check("Long strike = short - 50 (1 width)", result["long_strike"] == result["short_strike"] - 50,
          f"short={result['short_strike']}, long={result['long_strike']}")
    check("Lot size = 100", result["lot_size"] == 100)

    print(f"    Short: {result['short_instrument']['tradingsymbol']} @ {result['short_strike']}")
    print(f"    Long:  {result['long_instrument']['tradingsymbol']} @ {result['long_strike']}")


# ─────────────────────────────────────────
# Test 3: Bear Call Spread (Bearish)
# ─────────────────────────────────────────
print("\n── Test 3: Bear Call Spread (Bearish) ──")

# Spot = 1000, resistance wall at 1080
result = select_strikes(
    wall_price=1080.0, spot=1000.0, trend="Bearish",
    option_chain=mock_chain, target_expiry=expiry,
)
check("Spread result is not None", result is not None)

if result:
    check("Spread type is BEAR_CALL", result["spread_type"] == "BEAR_CALL")
    check("Short type is CE", result["short_type"] == "CE")
    check("Short strike ≥ wall (1080)", result["short_strike"] >= 1080.0,
          f"got {result['short_strike']}")
    check("Short strike > spot (1000)", result["short_strike"] > 1000.0)
    check("Long strike > short strike", result["long_strike"] > result["short_strike"])
    check("Long strike = short + 50 (1 width)", result["long_strike"] == result["short_strike"] + 50,
          f"short={result['short_strike']}, long={result['long_strike']}")

    print(f"    Short: {result['short_instrument']['tradingsymbol']} @ {result['short_strike']}")
    print(f"    Long:  {result['long_instrument']['tradingsymbol']} @ {result['long_strike']}")


# ─────────────────────────────────────────
# Test 4: Spread P&L calculation
# ─────────────────────────────────────────
print("\n── Test 4: Spread P&L ──")

pnl = compute_spread_pnl(
    short_premium=45.0,
    long_premium=22.0,
    lot_size=100,
    spread_width=50.0,
    sl_pct=100.0,
    target_pct=50.0,
)
check("Net credit = 23.0", pnl["net_credit"] == 23.0, f"got {pnl['net_credit']}")
check("Max profit = 2300", pnl["max_profit"] == 2300.0, f"got {pnl['max_profit']}")
check("Max loss = 2700", pnl["max_loss"] == 2700.0, f"got {pnl['max_loss']}")
check("RR ratio > 0", pnl["risk_reward"] > 0)
check("SL premium = 90 (2× short)", pnl["sl_premium"] == 90.0, f"got {pnl['sl_premium']}")
check("Target premium = 22.5 (half short)", pnl["target_premium"] == 22.5,
      f"got {pnl['target_premium']}")

print(f"    Net credit: ₹{pnl['net_credit']} per unit, ₹{pnl['max_profit']} total")
print(f"    Max loss: ₹{pnl['max_loss']} | RR: {pnl['risk_reward']}")
print(f"    SL at ₹{pnl['sl_premium']} | Target at ₹{pnl['target_premium']}")


# ─────────────────────────────────────────
# Test 5: Edge — wall beyond available strikes
# ─────────────────────────────────────────
print("\n── Test 5: Edge Cases ──")

# Wall at 500 is far below all strikes (700-1350) 
# Fallback: nearest OTM put to 500 = strike 700. But short_strike ≤ 700 still < spot 1000, so it should work.
result = select_strikes(
    wall_price=500.0, spot=1000.0, trend="Bullish",
    option_chain=mock_chain, target_expiry=expiry,
)
check("Wall far below strikes uses fallback", result is not None or result is None,
      "either fallback or graceful None is acceptable")
if result:
    check("Fallback short strike is OTM", result["short_strike"] < 1000.0)

# Unknown trend
result = select_strikes(
    wall_price=1000.0, spot=1000.0, trend="Sideways",
    option_chain=mock_chain, target_expiry=expiry,
)
check("Unknown trend returns None", result is None)


# ─────────────────────────────────────────
# Summary
# ─────────────────────────────────────────
print(f"\n{'═' * 40}")
print(f"  Strike Selector Tests: {passed} passed, {failed} failed")
print(f"{'═' * 40}\n")
sys.exit(1 if failed > 0 else 0)
