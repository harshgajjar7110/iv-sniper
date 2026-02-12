"""
Test Volume Profile — verify VP calculation, Value Area, HVN detection.

Uses synthetic candle data with a known volume concentration.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyst.volume_profile import (
    calculate_volume_profile,
    find_hvn_walls,
    _freedman_diaconis_bin_width,
)
import config
import pandas as pd

# Override the ADV threshold for testing with synthetic data
config.VP_MIN_ADV = 0

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
# Test 1: Freedman-Diaconis bin width
# ─────────────────────────────────────────
print("\n── Test 1: Bin Width Computation ──")

# Tight range stock
tight = pd.Series([100 + i * 0.1 for i in range(60)])
bw_tight = _freedman_diaconis_bin_width(tight)
check("Tight-range bin width is small", 0.5 <= bw_tight <= 5.0, f"got {bw_tight}")

# Wide range stock
wide = pd.Series([1000 + i * 50 for i in range(60)])
bw_wide = _freedman_diaconis_bin_width(wide)
check("Wide-range bin width is larger", bw_wide > bw_tight, f"got {bw_wide}")

# Zero IQR (flat stock)
flat = pd.Series([500] * 60)
bw_flat = _freedman_diaconis_bin_width(flat)
check("Flat stock falls back to 0.5% of median", bw_flat > 0, f"got {bw_flat}")


# ─────────────────────────────────────────
# Test 2: Volume Profile calculation
# ─────────────────────────────────────────
print("\n── Test 2: Volume Profile ──")

# Create 60 candles with heavy volume concentrated at 100-110 range
candles = []
for i in range(60):
    if i < 40:  # 40 days trading in 100-110 range with high volume
        candles.append({
            "open": 102, "high": 110, "low": 100, "close": 105,
            "volume": 1_000_000,
        })
    else:  # 20 days trading in 130-140 range with lower volume
        candles.append({
            "open": 132, "high": 140, "low": 130, "close": 135,
            "volume": 200_000,
        })

# Use fixed bin_size=5 for deterministic results
profile = calculate_volume_profile(candles, bin_size=5.0)
check("Profile is not None", profile is not None)

if profile:
    check("POC is in the 100-110 range", 100 <= profile["poc"] <= 110,
          f"got {profile['poc']}")
    check("VA_low <= POC", profile["va_low"] <= profile["poc"])
    check("VA_high >= POC", profile["va_high"] >= profile["poc"])
    check("Total volume > 0", profile["total_volume"] > 0)

    # Value Area should capture roughly 70% of volume
    va_bins = {
        p: v for p, v in profile["bins"].items()
        if profile["va_low"] <= p <= profile["va_high"]
    }
    va_vol = sum(va_bins.values())
    va_pct = (va_vol / profile["total_volume"]) * 100
    check("Value Area captures ~70% of volume", 65 <= va_pct <= 100,
          f"got {va_pct:.1f}%")

    print(f"\n    POC = {profile['poc']}, VA = [{profile['va_low']}, {profile['va_high']}]")
    print(f"    Bin size = {profile['bin_size']}, VA volume = {va_pct:.1f}%")


# ─────────────────────────────────────────
# Test 3: HVN Wall Detection
# ─────────────────────────────────────────
print("\n── Test 3: HVN Wall Detection ──")

if profile:
    # Spot at 120 — between the two clusters
    walls = find_hvn_walls(profile, spot_price=120.0)
    check("Support wall exists below 120",
          walls["support_wall"] is not None and walls["support_wall"] < 120,
          f"got {walls['support_wall']}")
    # 130-140 zone has only 200K vol vs 1M at 100-110 — correctly NOT an HVN
    check("Resistance wall is None (low vol zone isn't HVN)",
          walls["resistance_wall"] is None,
          f"got {walls['resistance_wall']}")
    check("At least 1 HVN found", len(walls["all_hvns"]) >= 1,
          f"got {len(walls['all_hvns'])}")

    print(f"\n    Support wall = {walls['support_wall']}")
    print(f"    Resistance wall = {walls['resistance_wall']} (correct: low-vol zone)")
    print(f"    HVN count = {len(walls['all_hvns'])}")

    # Test with concentrated volume spikes → both walls should exist
    candles_balanced = []
    # Background: wide-range, low-volume candles spanning 80-160
    for i in range(20):
        candles_balanced.append({"open": 90, "high": 160, "low": 80, "close": 120, "volume": 100_000})
    # Spike below 120: tight range 105-110, high volume
    for i in range(20):
        candles_balanced.append({"open": 106, "high": 110, "low": 105, "close": 108, "volume": 2_000_000})
    # Spike above 120: tight range 135-140, high volume
    for i in range(20):
        candles_balanced.append({"open": 136, "high": 140, "low": 135, "close": 138, "volume": 2_000_000})
    profile2 = calculate_volume_profile(candles_balanced, bin_size=5.0)
    walls2 = find_hvn_walls(profile2, spot_price=120.0)
    check("Concentrated spikes: both walls found",
          walls2["support_wall"] is not None and walls2["resistance_wall"] is not None,
          f"support={walls2['support_wall']}, resist={walls2['resistance_wall']}")

    print(f"\n    Support wall = {walls['support_wall']}")
    print(f"    Resistance wall = {walls['resistance_wall']}")
    print(f"    HVN count = {len(walls['all_hvns'])}")


# ─────────────────────────────────────────
# Test 4: Edge case — too few candles
# ─────────────────────────────────────────
print("\n── Test 4: Edge Cases ──")

result = calculate_volume_profile([{"open": 1, "high": 2, "low": 1, "close": 1.5, "volume": 100}] * 5)
check("Too few candles returns None", result is None)


# ─────────────────────────────────────────
# Summary
# ─────────────────────────────────────────
print(f"\n{'═' * 40}")
print(f"  Volume Profile Tests: {passed} passed, {failed} failed")
print(f"{'═' * 40}\n")
sys.exit(1 if failed > 0 else 0)
