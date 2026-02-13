"""
Unit Tests for Validation Utility Module

Tests all validation functions in ui/utils/validation.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.utils.validation import (
    validate_symbol,
    validate_option_symbol,
    validate_strike_price,
    validate_spread_strikes,
    validate_quantity,
    validate_lot_size,
    validate_premium,
    validate_spread_credit,
    validate_expiry_date,
    validate_expiry_is_thursday,
    validate_trade_data,
    validate_spread_data,
    validate_capital_config,
    validate_positive_number,
    validate_percentage,
    validate_range,
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
# Symbol Validation Tests
# ═════════════════════════════════════════════════════════════════════════════
print("\n── Symbol Validation ──")

check("Valid symbol: NIFTY", validate_symbol("NIFTY"))
check("Valid symbol: RELIANCE", validate_symbol("RELIANCE"))
check("Invalid symbol: empty", not validate_symbol(""))
check("Invalid symbol: None", not validate_symbol(None))
check("Invalid symbol: special chars", not validate_symbol("NIFTY@123"))
check("Invalid symbol: too long", not validate_symbol("A" * 25))

# Option Symbol Validation
print("\n── Option Symbol Validation ──")

check("Valid option: NFO:NIFTY24FEB21500CE", validate_option_symbol("NFO:NIFTY24FEB21500CE"))
check("Valid option: NIFTY24FEB21500PE", validate_option_symbol("NIFTY24FEB21500PE"))
check("Invalid option: no type", not validate_option_symbol("NIFTY24FEB21500"))
check("Invalid option: wrong type", not validate_option_symbol("NIFTY24FEB21500XX"))
check("Invalid option: too short", not validate_option_symbol("NIFTY24FEB"))


# ═════════════════════════════════════════════════════════════════════════════
# Strike Price Validation Tests
# ═════════════════════════════════════════════════════════════════════════════
print("\n── Strike Price Validation ──")

check("Valid strike: 21500", validate_strike_price(21500))
check("Valid strike: 45000.5", validate_strike_price(45000.5))
check("Invalid strike: negative", not validate_strike_price(-100))
check("Invalid strike: too high", not validate_strike_price(200000))
check("Invalid strike: string", not validate_strike_price("abc"))

# Spread Strikes Validation
print("\n── Spread Strikes Validation ──")

check("Bull Put: 22000 > 21500", validate_spread_strikes(22000, 21500, "BULL_PUT"))
check("Bear Call: 21000 < 21500", validate_spread_strikes(21000, 21500, "BEAR_CALL"))
check("Invalid Bull Put: short < long", not validate_spread_strikes(21000, 21500, "BULL_PUT"))
check("Invalid Bear Call: short > long", not validate_spread_strikes(22000, 21500, "BEAR_CALL"))
check("Invalid strategy", not validate_spread_strikes(22000, 21500, "UNKNOWN"))


# ═════════════════════════════════════════════════════════════════════════════
# Quantity Validation Tests
# ═════════════════════════════════════════════════════════════════════════════
print("\n── Quantity Validation ──")

check("Valid quantity: 75", validate_quantity(75))
check("Valid quantity: 150", validate_quantity(150))
check("Invalid quantity: 0", not validate_quantity(0))
check("Invalid quantity: negative", not validate_quantity(-10))
check("Invalid quantity: too high", not validate_quantity(20000))

# Lot Size Validation
print("\n── Lot Size Validation ──")

check("Valid lot: 75 (NIFTY)", validate_lot_size(75, 75))
check("Valid lot: 150 (2x NIFTY)", validate_lot_size(150, 75))
check("Invalid lot: 50", not validate_lot_size(50, 75))
check("Invalid lot: 100", not validate_lot_size(100, 75))


# ═════════════════════════════════════════════════════════════════════════════
# Premium Validation Tests
# ═════════════════════════════════════════════════════════════════════════════
print("\n── Premium Validation ──")

check("Valid premium: 45.5", validate_premium(45.5))
check("Valid premium: 0", validate_premium(0, min_premium=0))
check("Invalid premium: negative", not validate_premium(-5))
check("Invalid premium: too high", not validate_premium(50000))

# Spread Credit Validation
print("\n── Spread Credit Validation ──")

check("Valid credit: 25.5", validate_spread_credit(25.5))
check("Valid credit: 0.5", validate_spread_credit(0.5))
check("Invalid credit: 0", not validate_spread_credit(0))
check("Invalid credit: negative", not validate_spread_credit(-10))


# ═════════════════════════════════════════════════════════════════════════════
# Date/Expiry Validation Tests
# ═════════════════════════════════════════════════════════════════════════════
print("\n── Expiry Date Validation ──")

from datetime import date, timedelta

today = date.today()
future_date = today + timedelta(days=15)
past_date = today - timedelta(days=5)
far_future = today + timedelta(days=400)

check("Valid expiry: 15 days", validate_expiry_date(future_date.isoformat()))
check("Invalid expiry: past", not validate_expiry_date(past_date.isoformat()))
check("Invalid expiry: too far", not validate_expiry_date(far_future.isoformat()))

# Thursday Validation
print("\n── Thursday Expiry Validation ──")

# Find next Thursday
days_until_thursday = (3 - today.weekday()) % 7
next_thursday = today + timedelta(days=days_until_thursday if days_until_thursday > 0 else 7)
next_friday = next_thursday + timedelta(days=1)

check("Valid: Thursday", validate_expiry_is_thursday(next_thursday.isoformat()))
check("Invalid: Friday", not validate_expiry_is_thursday(next_friday.isoformat()))


# ═════════════════════════════════════════════════════════════════════════════
# Trade Data Validation Tests
# ═════════════════════════════════════════════════════════════════════════════
print("\n── Trade Data Validation ──")

valid_trade = {
    'symbol': 'NIFTY',
    'short_strike': 22000,
    'long_strike': 21500,
    'strategy': 'BULL_PUT',
    'expiry': (today + timedelta(days=15)).isoformat(),
}

invalid_trade_missing = {
    'symbol': 'NIFTY',
    'short_strike': 22000,
}

invalid_trade_strikes = {
    'symbol': 'NIFTY',
    'short_strike': 21000,  # Wrong for BULL_PUT
    'long_strike': 21500,
    'strategy': 'BULL_PUT',
    'expiry': (today + timedelta(days=15)).isoformat(),
}

is_valid, error = validate_trade_data(valid_trade)
check("Valid trade data", is_valid, error or "")

is_valid, error = validate_trade_data(invalid_trade_missing)
check("Invalid: missing fields", not is_valid)

is_valid, error = validate_trade_data(invalid_trade_strikes)
check("Invalid: wrong strikes", not is_valid)


# ═════════════════════════════════════════════════════════════════════════════
# Configuration Validation Tests
# ═════════════════════════════════════════════════════════════════════════════
print("\n── Capital Configuration Validation ──")

check("Valid capital: 500000", validate_capital_config(500000))
check("Valid capital: 1000000", validate_capital_config(1000000))
check("Invalid capital: too low", not validate_capital_config(5000))
check("Invalid capital: too high", not validate_capital_config(200000000))


# ═════════════════════════════════════════════════════════════════════════════
# Numeric Range Validation Tests
# ═════════════════════════════════════════════════════════════════════════════
print("\n── Numeric Range Validation ──")

check("Positive: 5", validate_positive_number(5))
check("Positive: 0 allowed", validate_positive_number(0, allow_zero=True))
check("Not positive: 0", not validate_positive_number(0))
check("Not positive: -5", not validate_positive_number(-5))

check("Valid percentage: 50", validate_percentage(50))
check("Valid percentage: 0 allowed", validate_percentage(0))
check("Valid percentage: 100", validate_percentage(100))
check("Invalid percentage: 101", not validate_percentage(101))
check("Invalid percentage: -1", not validate_percentage(-1))

check("In range: 50 in 0-100", validate_range(50, 0, 100))
check("In range: boundary", validate_range(0, 0, 100))
check("Out of range: -10", not validate_range(-10, 0, 100))
check("Out of range: 150", not validate_range(150, 0, 100))


# ═════════════════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════════════════
print(f"\n{'═' * 50}")
print(f"  Validation Tests: {passed} passed, {failed} failed")
print(f"{'═' * 50}\n")

sys.exit(1 if failed > 0 else 0)
