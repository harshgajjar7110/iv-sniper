"""
Unit Tests for Formatting Utility Module

Tests all formatting functions in ui/utils/formatting.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, datetime, timedelta
from ui.utils.formatting import (
    format_currency,
    format_currency_compact,
    format_margin,
    format_premium,
    format_percentage,
    format_percentage_change,
    format_date,
    format_time,
    format_datetime,
    format_time_12h,
    format_expiry_date,
    format_relative_time,
    format_number,
    format_integer,
    format_compact_number,
    format_pnl,
    format_pnl_with_delta,
    format_pnl_percentage,
    get_pnl_color,
    format_strike,
    format_spread_strikes,
    format_trade_status,
    format_strategy,
    format_trade_summary,
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
# Currency Formatting Tests
# ═════════════════════════════════════════════════════════════════════════════
print("\n── Currency Formatting ──")

check("Format ₹1,234.56", format_currency(1234.56) == "₹1,234.56")
check("Format ₹0.00", format_currency(0) == "₹0.00")
check("Format no symbol", format_currency(1234.56, include_symbol=False) == "1,234.56")
check("Format 2 decimals", format_currency(1234.5, decimals=2) == "₹1,234.50")

# Compact Currency
print("\n── Compact Currency ──")

check("Compact ₹950", format_currency_compact(950) == "₹950")
check("Compact ₹1.2K", format_currency_compact(1250) == "₹1.2K")
check("Compact ₹1.5L", format_currency_compact(150000) == "₹1.5L")
check("Compact ₹2.5Cr", format_currency_compact(25000000) == "₹2.5Cr")

# Margin Formatting
print("\n── Margin Formatting ──")

check("Margin ₹1,00,000", format_margin(100000) == "₹100,000")
check("Margin ₹0", format_margin(0) == "₹0")

# Premium Formatting
print("\n── Premium Formatting ──")

check("Premium ₹45.50", format_premium(45.5) == "₹45.50")
check("Premium ₹0.00", format_premium(0) == "₹0.00")


# ═════════════════════════════════════════════════════════════════════════════
# Percentage Formatting Tests
# ═════════════════════════════════════════════════════════════════════════════
print("\n── Percentage Formatting ──")

check("Format 75.5%", format_percentage(75.5) == "75.5%")
check("Format 0%", format_percentage(0) == "0.0%")
check("Format no symbol", format_percentage(75.5, include_symbol=False) == "75.5")
check("Format 0 decimals", format_percentage(75.5, decimals=0) == "76%")

# Percentage Change
print("\n── Percentage Change ──")

check("Change +50%", format_percentage_change(100, 150) == "+50.0%")
check("Change -25%", format_percentage_change(100, 75) == "-25.0%")
check("Change 0%", format_percentage_change(100, 100) == "+0.0%")
check("Change N/A", format_percentage_change(0, 100) == "N/A")


# ═════════════════════════════════════════════════════════════════════════════
# Date/Time Formatting Tests
# ═════════════════════════════════════════════════════════════════════════════
print("\n── Date Formatting ──")

test_date = date(2026, 2, 15)
test_datetime = datetime(2026, 2, 15, 14, 30, 0)

check("Date YYYY-MM-DD", format_date(test_date) == "2026-02-15")
check("Date custom format", format_date(test_date, "%d-%b-%Y") == "15-Feb-2026")
check("Date from string", format_date("2026-02-15") == "2026-02-15")

# Time Formatting
print("\n── Time Formatting ──")

check("Time HH:MM:SS", format_time(test_datetime) == "14:30:00")
check("Time 12h", format_time_12h(test_datetime) == "02:30 PM")

# Datetime Formatting
print("\n── Datetime Formatting ──")

check("Datetime default", format_datetime(test_datetime) == "2026-02-15 14:30:00")
check("Datetime custom", format_datetime(test_datetime, "%d-%b-%Y %I:%M %p") == "15-Feb-2026 02:30 PM")

# Expiry Date Formatting
print("\n── Expiry Date Formatting ──")

check("Expiry Feb 2026", format_expiry_date(test_date) == "Feb 2026")
check("Expiry from string", format_expiry_date("2026-02-15") == "Feb 2026")

# Relative Time
print("\n── Relative Time ──")

just_now = datetime.now() - timedelta(seconds=30)
five_min_ago = datetime.now() - timedelta(minutes=5)
two_hours_ago = datetime.now() - timedelta(hours=2)

check("Relative: Just now", format_relative_time(just_now) == "Just now")
check("Relative: 5m ago", format_relative_time(five_min_ago) == "5m ago")
check("Relative: 2h ago", format_relative_time(two_hours_ago) == "2h ago")


# ═════════════════════════════════════════════════════════════════════════════
# Number Formatting Tests
# ═════════════════════════════════════════════════════════════════════════════
print("\n── Number Formatting ──")

check("Number 1,234.56", format_number(1234.56) == "1,234.56")
check("Number 0 decimals", format_number(1234.56, decimals=0) == "1,235")
check("Integer 1,234", format_integer(1234) == "1,234")

# Compact Number
print("\n── Compact Number ──")

check("Compact 950", format_compact_number(950) == "950")
check("Compact 1.2K", format_compact_number(1250) == "1.2K")
check("Compact 1.5L", format_compact_number(150000) == "1.5L")
check("Compact 2.5Cr", format_compact_number(25000000) == "2.5Cr")


# ═════════════════════════════════════════════════════════════════════════════
# P&L Formatting Tests
# ═════════════════════════════════════════════════════════════════════════════
print("\n── P&L Formatting ──")

check("PnL positive", format_pnl(1234) == "₹+1,234")
check("PnL negative", format_pnl(-1234) == "₹-1,234")
check("PnL zero", format_pnl(0) == "₹+0")
check("PnL no symbol", format_pnl(1234, include_symbol=False) == "+1,234")

# P&L with Delta
print("\n── P&L with Delta ──")

formatted, delta = format_pnl_with_delta(1234)
check("PnL delta formatted", formatted == "₹1,234")
check("PnL delta string", delta == "+₹1,234")

# P&L Percentage
print("\n── P&L Percentage ──")

check("PnL % positive", format_pnl_percentage(10000, 100000) == "+10.0%")
check("PnL % negative", format_pnl_percentage(-5000, 100000) == "-5.0%")
check("PnL % zero capital", format_pnl_percentage(10000, 0) == "N/A")

# P&L Color
print("\n── P&L Color ──")

check("Color: profit", get_pnl_color(100) == "normal")
check("Color: loss", get_pnl_color(-100) == "inverse")
check("Color: zero", get_pnl_color(0) == "normal")


# ═════════════════════════════════════════════════════════════════════════════
# Strike Price Formatting Tests
# ═════════════════════════════════════════════════════════════════════════════
print("\n── Strike Price Formatting ──")

check("Strike 21,500", format_strike(21500) == "21,500")
check("Strike 1,00,000", format_strike(100000) == "100,000")
check("Spread strikes", format_spread_strikes(22000, 21500) == "22,000 / 21,500")


# ═════════════════════════════════════════════════════════════════════════════
# Trade Status Formatting Tests
# ═════════════════════════════════════════════════════════════════════════════
print("\n── Trade Status Formatting ──")

check("Status OPEN", "OPEN" in format_trade_status("OPEN"))
check("Status CLOSED", "CLOSED" in format_trade_status("CLOSED"))
check("Strategy Bull Put", format_strategy("BULL_PUT") == "Bull Put")
check("Strategy Bear Call", format_strategy("BEAR_CALL") == "Bear Call")

# Trade Summary
print("\n── Trade Summary ──")

test_trade = {
    'symbol': 'NIFTY',
    'strategy': 'BULL_PUT',
    'short_strike': 22000,
    'long_strike': 21500,
}
check("Trade summary", format_trade_summary(test_trade) == "NIFTY Bull Put 22,000/21,500")


# ═════════════════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════════════════
print(f"\n{'═' * 50}")
print(f"  Formatting Tests: {passed} passed, {failed} failed")
print(f"{'═' * 50}\n")

sys.exit(1 if failed > 0 else 0)
