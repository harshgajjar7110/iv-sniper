"""
Unit Tests for Symbol Utility Module

Tests all functions in ui/utils/symbol_utils.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from ui.utils.symbol_utils import (
    parse_zerodha_symbol,
    calculate_expiry_date,
    reconstruct_option_symbol,
    get_option_symbols_for_trade,
    get_all_trade_symbols,
    get_trade_symbols_dict,
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


# ═════════════════════════════════════════════════════════════════════════════
# Parse Zerodha Symbol Tests
# ═════════════════════════════════════════════════════════════════════════════
print("\n── Parse Zerodha Symbol ──")

# Test NIFTY symbol
result = parse_zerodha_symbol("NFO:NIFTY24FEB21500CE")
check("Parse NIFTY CE", 
      result and result['symbol'] == 'NIFTY' and result['option_type'] == 'CE',
      f"Got: {result}")

# Test RELIANCE symbol
result = parse_zerodha_symbol("RELIANCE24MAR3000PE")
check("Parse RELIANCE PE",
      result and result['symbol'] == 'RELIANCE' and result['option_type'] == 'PE',
      f"Got: {result}")

# Test with different months
result = parse_zerodha_symbol("NIFTY25JAN22000CE")
check("Parse JAN expiry",
      result and result['month'] == 'JAN',
      f"Got: {result}")

result = parse_zerodha_symbol("NIFTY25DEC22000CE")
check("Parse DEC expiry",
      result and result['month'] == 'DEC',
      f"Got: {result}")

# Test invalid symbols
result = parse_zerodha_symbol("INVALID")
check("Invalid symbol returns None", result is None)

result = parse_zerodha_symbol("")
check("Empty symbol returns None", result is None)


# ═════════════════════════════════════════════════════════════════════════════
# Calculate Expiry Date Tests
# ═════════════════════════════════════════════════════════════════════════════
print("\n── Calculate Expiry Date ──")

# Test for 2026
expiry = calculate_expiry_date(2026, 2)  # February 2026
check("Feb 2026 expiry is Thursday", expiry.weekday() == 3, f"Got: {expiry}")

expiry = calculate_expiry_date(2026, 12)  # December 2026
check("Dec 2026 expiry is Thursday", expiry.weekday() == 3, f"Got: {expiry}")

# Test leap year
expiry = calculate_expiry_date(2024, 2)  # February 2024 (leap year)
check("Feb 2024 (leap) expiry is Thursday", expiry.weekday() == 3, f"Got: {expiry}")


# ═════════════════════════════════════════════════════════════════════════════
# Reconstruct Option Symbol Tests
# ═════════════════════════════════════════════════════════════════════════════
print("\n── Reconstruct Option Symbol ──")

# Test BULL_PUT (PE option)
result = reconstruct_option_symbol(
    symbol="NIFTY",
    expiry="2026-02-27",
    strike=21500,
    strategy="BULL_PUT",
    include_exchange=True
)
check("Reconstruct NIFTY PE with exchange",
      result == "NFO:NIFTY26FEB21500PE",
      f"Got: {result}")

# Test BEAR_CALL (CE option)
result = reconstruct_option_symbol(
    symbol="NIFTY",
    expiry="2026-02-27",
    strike=22000,
    strategy="BEAR_CALL",
    include_exchange=False
)
check("Reconstruct NIFTY CE without exchange",
      result == "NIFTY26FEB22000CE",
      f"Got: {result}")

# Test RELIANCE
result = reconstruct_option_symbol(
    symbol="RELIANCE",
    expiry="2026-03-26",
    strike=3000,
    strategy="BULL_PUT",
    include_exchange=True
)
check("Reconstruct RELIANCE PE",
      result == "NFO:RELIANCE26MAR3000PE",
      f"Got: {result}")


# ═════════════════════════════════════════════════════════════════════════════
# Get Option Symbols for Trade Tests
# ═════════════════════════════════════════════════════════════════════════════
print("\n── Get Option Symbols for Trade ──")

result = get_option_symbols_for_trade(
    symbol="NIFTY",
    expiry="2026-02-27",
    short_strike=22000,
    long_strike=21500,
    strategy="BULL_PUT"
)

check("Bull Put symbols returned",
      'short_symbol' in result and 'long_symbol' in result,
      f"Got: {result}")

check("Bull Put short is PE",
      'PE' in result['short_symbol'],
      f"Got: {result.get('short_symbol')}")

check("Bull Put long is PE",
      'PE' in result['long_symbol'],
      f"Got: {result.get('long_symbol')}")

# Test Bear Call
result = get_option_symbols_for_trade(
    symbol="NIFTY",
    expiry="2026-02-27",
    short_strike=21000,
    long_strike=21500,
    strategy="BEAR_CALL"
)

check("Bear Call short is CE",
      'CE' in result['short_symbol'],
      f"Got: {result.get('short_symbol')}")

check("Bear Call long is CE",
      'CE' in result['long_symbol'],
      f"Got: {result.get('long_symbol')}")


# ═════════════════════════════════════════════════════════════════════════════
# Get All Trade Symbols Tests
# ═════════════════════════════════════════════════════════════════════════════
print("\n── Get All Trade Symbols ──")

trades = [
    {
        'symbol': 'NIFTY',
        'expiry': '2026-02-27',
        'short_strike': 22000,
        'long_strike': 21500,
        'strategy': 'BULL_PUT'
    },
    {
        'symbol': 'RELIANCE',
        'expiry': '2026-03-26',
        'short_strike': 3000,
        'long_strike': 2900,
        'strategy': 'BULL_PUT'
    }
]

result = get_all_trade_symbols(trades)
check("Returns list of symbols",
      isinstance(result, list) and len(result) == 4,
      f"Got: {result}")

check("Contains NIFTY symbols",
      any('NIFTY' in s for s in result),
      f"Got: {result}")

check("Contains RELIANCE symbols",
      any('RELIANCE' in s for s in result),
      f"Got: {result}")

# Empty trades
result = get_all_trade_symbols([])
check("Empty trades returns empty list",
      result == [],
      f"Got: {result}")


# ═════════════════════════════════════════════════════════════════════════════
# Get Trade Symbols Dict Tests
# ═════════════════════════════════════════════════════════════════════════════
print("\n── Get Trade Symbols Dict ──")

trades = [
    {
        'trade_id': 'trade-001',
        'symbol': 'NIFTY',
        'expiry': '2026-02-27',
        'short_strike': 22000,
        'long_strike': 21500,
        'strategy': 'BULL_PUT'
    }
]

result = get_trade_symbols_dict(trades)
check("Returns dict with trade_id keys",
      isinstance(result, dict) and 'trade-001' in result,
      f"Got: {result}")

check("Contains short and long symbols",
      'short_symbol' in result['trade-001'] and 'long_symbol' in result['trade-001'],
      f"Got: {result.get('trade-001')}")


# ═════════════════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════════════════
print(f"\n{'═' * 50}")
print(f"  Symbol Utils Tests: {passed} passed, {failed} failed")
print(f"{'═' * 50}\n")

sys.exit(1 if failed > 0 else 0)
