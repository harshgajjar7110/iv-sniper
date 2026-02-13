"""
Formatting Utility Module

Provides centralized formatting functions for:
- Currency formatting (Indian Rupee)
- Percentage formatting
- Date/time formatting
- Number formatting (compact, scientific)
- P&L formatting with colors
- Strike price formatting
- Trade status formatting
"""

from datetime import datetime, date, time
from typing import Optional, Union


# =============================================================================
# Currency Formatting (Indian Rupee)
# =============================================================================

def format_currency(amount: Union[int, float], decimals: int = 2, include_symbol: bool = True) -> str:
    """
    Format amount as Indian Rupee currency.
    
    Args:
        amount: Amount to format
        decimals: Number of decimal places (default: 2)
        include_symbol: Whether to include ₹ symbol (default: True)
    
    Returns:
        Formatted currency string (e.g., "₹1,234.56" or "1234.56")
    """
    try:
        value = float(amount)
        
        if include_symbol:
            # Use Indian number system (lakhs, crores)
            return f"₹{value:,.{decimals}f}"
        else:
            return f"{value:,.{decimals}f}"
    except (ValueError, TypeError):
        return "₹0.00" if include_symbol else "0.00"


def format_currency_compact(amount: Union[int, float]) -> str:
    """
    Format large currency amounts in compact form (L, Cr).
    
    Args:
        amount: Amount to format
    
    Returns:
        Compact currency string (e.g., "₹1.2L" or "₹2.5Cr")
    """
    try:
        value = float(amount)
        
        if value >= 10000000:  # >= 1 Crore
            return f"₹{value / 10000000:.1f}Cr"
        elif value >= 100000:  # >= 1 Lakh
            return f"₹{value / 100000:.1f}L"
        elif value >= 1000:  # >= 1 Thousand
            return f"₹{value / 1000:.1f}K"
        else:
            return f"₹{value:.0f}"
    except (ValueError, TypeError):
        return "₹0"


def format_margin(amount: Union[int, float]) -> str:
    """
    Format margin amounts with appropriate precision.
    
    Args:
        amount: Margin amount
    
    Returns:
        Formatted margin string (e.g., "₹1,23,456")
    """
    return format_currency(amount, decimals=0, include_symbol=True)


def format_premium(premium: Union[int, float]) -> str:
    """
    Format option premium with standard precision.
    
    Args:
        premium: Premium amount
    
    Returns:
        Formatted premium string (e.g., "₹45.50")
    """
    return format_currency(premium, decimals=2, include_symbol=True)


# =============================================================================
# Percentage Formatting
# =============================================================================

def format_percentage(value: Union[int, float], decimals: int = 1, include_symbol: bool = True) -> str:
    """
    Format value as percentage.
    
    Args:
        value: Value to format as percentage
        decimals: Number of decimal places (default: 1)
        include_symbol: Whether to include % symbol (default: True)
    
    Returns:
        Formatted percentage string (e.g., "75.5%" or "75.5")
    """
    try:
        value = float(value)
        
        if include_symbol:
            return f"{value:.{decimals}f}%"
        else:
            return f"{value:.{decimals}f}"
    except (ValueError, TypeError):
        return "0.0%" if include_symbol else "0.0"


def format_percentage_change(old_value: Union[int, float], new_value: Union[int, float]) -> str:
    """
    Calculate and format percentage change between two values.
    
    Args:
        old_value: Original value
        new_value: New value
    
    Returns:
        Formatted percentage change (e.g., "+15.2%" or "-8.5%")
    """
    try:
        old = float(old_value)
        new = float(new_value)
        
        if old == 0:
            return "N/A"
        
        change = ((new - old) / old) * 100
        sign = "+" if change >= 0 else ""
        
        return f"{sign}{change:.1f}%"
    except (ValueError, TypeError, ZeroDivisionError):
        return "N/A"


def format_iv_score(score: Union[int, float]) -> str:
    """
    Format IV score with appropriate color indicator.
    
    Args:
        score: IV score (0-100)
    
    Returns:
        Formatted IV score string (e.g., "75%")
    """
    return format_percentage(score, decimals=0)


# =============================================================================
# Date/Time Formatting
# =============================================================================

def format_date(date_obj: Union[str, date, datetime], format_str: str = "%Y-%m-%d") -> str:
    """
    Format date object to string.
    
    Args:
        date_obj: Date to format (string, date, or datetime)
        format_str: Output format string (default: "%Y-%m-%d")
    
    Returns:
        Formatted date string
    """
    try:
        if isinstance(date_obj, str):
            # Try parsing ISO format first
            if 'T' in date_obj:
                date_obj = datetime.fromisoformat(date_obj.replace('Z', '+00:00'))
            else:
                date_obj = datetime.strptime(date_obj, "%Y-%m-%d").date()
        
        if isinstance(date_obj, datetime):
            return date_obj.strftime(format_str)
        elif isinstance(date_obj, date):
            return date_obj.strftime(format_str)
        else:
            return str(date_obj)
    except (ValueError, TypeError):
        return "N/A"


def format_time(time_obj: Union[str, time, datetime], format_str: str = "%H:%M:%S") -> str:
    """
    Format time object to string.
    
    Args:
        time_obj: Time to format (string, time, or datetime)
        format_str: Output format string (default: "%H:%M:%S")
    
    Returns:
        Formatted time string
    """
    try:
        if isinstance(time_obj, str):
            if 'T' in time_obj:
                time_obj = datetime.fromisoformat(time_obj.replace('Z', '+00:00'))
                return time_obj.strftime(format_str)
            else:
                return time_obj
        
        if isinstance(time_obj, datetime):
            return time_obj.strftime(format_str)
        elif isinstance(time_obj, time):
            return time_obj.strftime(format_str)
        else:
            return str(time_obj)
    except (ValueError, TypeError):
        return "N/A"


def format_datetime(dt_obj: Union[str, datetime], format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format datetime object to string.
    
    Args:
        dt_obj: Datetime to format (string or datetime)
        format_str: Output format string (default: "%Y-%m-%d %H:%M:%S")
    
    Returns:
        Formatted datetime string
    """
    try:
        if isinstance(dt_obj, str):
            if 'T' in dt_obj:
                dt_obj = datetime.fromisoformat(dt_obj.replace('Z', '+00:00'))
            else:
                dt_obj = datetime.strptime(dt_obj, "%Y-%m-%d %H:%M:%S")
        
        if isinstance(dt_obj, datetime):
            return dt_obj.strftime(format_str)
        else:
            return str(dt_obj)
    except (ValueError, TypeError):
        return "N/A"


def format_time_12h(dt_obj: Union[str, datetime]) -> str:
    """
    Format datetime in 12-hour format with AM/PM.
    
    Args:
        dt_obj: Datetime to format
    
    Returns:
        Formatted time string (e.g., "02:30 PM")
    """
    return format_time(dt_obj, "%I:%M %p")


def format_expiry_date(expiry: Union[str, date, datetime]) -> str:
    """
    Format expiry date in readable format.
    
    Args:
        expiry: Expiry date
    
    Returns:
        Formatted expiry string (e.g., "Feb 2026" or "25-Feb-2026")
    """
    try:
        if isinstance(expiry, str):
            if 'T' in expiry:
                expiry = datetime.fromisoformat(expiry.replace('Z', '+00:00'))
            else:
                expiry = datetime.strptime(expiry, "%Y-%m-%d")
        
        if isinstance(expiry, datetime):
            return expiry.strftime("%b %Y")
        elif isinstance(expiry, date):
            return expiry.strftime("%b %Y")
        else:
            return str(expiry)
    except (ValueError, TypeError):
        return "N/A"


def format_relative_time(dt_obj: Union[str, datetime]) -> str:
    """
    Format datetime as relative time (e.g., "2 hours ago").
    
    Args:
        dt_obj: Datetime to format
    
    Returns:
        Relative time string
    """
    try:
        if isinstance(dt_obj, str):
            if 'T' in dt_obj:
                dt_obj = datetime.fromisoformat(dt_obj.replace('Z', '+00:00'))
        
        if not isinstance(dt_obj, datetime):
            return "N/A"
        
        now = datetime.now()
        diff = now - dt_obj
        
        if diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            return f"{hours}h ago"
        elif diff.seconds >= 60:
            minutes = diff.seconds // 60
            return f"{minutes}m ago"
        else:
            return "Just now"
    except (ValueError, TypeError):
        return "N/A"


# =============================================================================
# Number Formatting
# =============================================================================

def format_number(value: Union[int, float], decimals: int = 2) -> str:
    """
    Format number with Indian thousand separators.
    
    Args:
        value: Number to format
        decimals: Number of decimal places
    
    Returns:
        Formatted number string (e.g., "1,234.56")
    """
    try:
        return f"{float(value):,.{decimals}f}"
    except (ValueError, TypeError):
        return "0"


def format_integer(value: Union[int, float]) -> str:
    """
    Format number as integer with thousand separators.
    
    Args:
        value: Number to format
    
    Returns:
        Formatted integer string (e.g., "1,234")
    """
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return "0"


def format_compact_number(value: Union[int, float]) -> str:
    """
    Format large numbers in compact form (K, L, Cr).
    
    Args:
        value: Number to format
    
    Returns:
        Compact number string (e.g., "1.2L")
    """
    try:
        val = float(value)
        
        if val >= 10000000:  # >= 1 Crore
            return f"{val / 10000000:.1f}Cr"
        elif val >= 100000:  # >= 1 Lakh
            return f"{val / 100000:.1f}L"
        elif val >= 1000:  # >= 1 Thousand
            return f"{val / 1000:.1f}K"
        else:
            return f"{val:.0f}"
    except (ValueError, TypeError):
        return "0"


def format_scientific(value: Union[int, float], decimals: int = 2) -> str:
    """
    Format number in scientific notation.
    
    Args:
        value: Number to format
        decimals: Number of decimal places
    
    Returns:
        Scientific notation string (e.g., "1.23e+05")
    """
    try:
        return f"{float(value):.{decimals}e}"
    except (ValueError, TypeError):
        return "0"


# =============================================================================
# P&L Formatting
# =============================================================================

def format_pnl(pnl: Union[int, float], include_symbol: bool = True) -> str:
    """
    Format profit/loss amount.
    
    Args:
        pnl: P&L amount
        include_symbol: Whether to include ₹ symbol
    
    Returns:
        Formatted P&L string (e.g., "₹+1,234" or "-₹1,234")
    """
    try:
        value = float(pnl)
        
        if include_symbol:
            sign = "+" if value >= 0 else ""
            return f"₹{sign}{value:,.0f}"
        else:
            sign = "+" if value >= 0 else ""
            return f"{sign}{value:,.0f}"
    except (ValueError, TypeError):
        return "₹0" if include_symbol else "0"


def format_pnl_with_delta(pnl: Union[int, float]) -> tuple[str, str]:
    """
    Format P&L with delta for Streamlit metrics.
    
    Args:
        pnl: P&L amount
    
    Returns:
        Tuple of (formatted_value, delta_string)
    """
    try:
        value = float(pnl)
        
        formatted = f"₹{value:,.0f}"
        sign = "+" if value >= 0 else ""
        delta = f"{sign}₹{value:,.0f}"
        
        return formatted, delta
    except (ValueError, TypeError):
        return "₹0", "₹0"


def format_pnl_percentage(pnl: Union[int, float], capital: Union[int, float]) -> str:
    """
    Format P&L as percentage of capital.
    
    Args:
        pnl: P&L amount
        capital: Total capital
    
    Returns:
        Formatted percentage string (e.g., "+12.5%")
    """
    try:
        pnl_val = float(pnl)
        capital_val = float(capital)
        
        if capital_val == 0:
            return "N/A"
        
        pct = (pnl_val / capital_val) * 100
        sign = "+" if pct >= 0 else ""
        
        return f"{sign}{pct:.1f}%"
    except (ValueError, TypeError, ZeroDivisionError):
        return "N/A"


def get_pnl_color(pnl: Union[int, float]) -> str:
    """
    Get color indicator for P&L value.
    
    Args:
        pnl: P&L amount
    
    Returns:
        Color string ("normal" for profit, "inverse" for loss)
    """
    try:
        value = float(pnl)
        
        if value > 0:
            return "normal"
        elif value < 0:
            return "inverse"
        else:
            return "normal"
    except (ValueError, TypeError):
        return "normal"


# =============================================================================
# Strike Price Formatting
# =============================================================================

def format_strike(strike: Union[int, float]) -> str:
    """
    Format strike price with thousand separators.
    
    Args:
        strike: Strike price
    
    Returns:
        Formatted strike string (e.g., "21,500")
    """
    try:
        return f"{int(strike):,}"
    except (ValueError, TypeError):
        return "0"


def format_spread_strikes(short_strike: Union[int, float], long_strike: Union[int, float]) -> str:
    """
    Format spread as strike range.
    
    Args:
        short_strike: Short leg strike
        long_strike: Long leg strike
    
    Returns:
        Formatted spread string (e.g., "21,500 / 21,000")
    """
    return f"{format_strike(short_strike)} / {format_strike(long_strike)}"


# =============================================================================
# Trade Status Formatting
# =============================================================================

def format_trade_status(status: str) -> str:
    """
    Format trade status with emoji indicator.
    
    Args:
        status: Trade status (OPEN, CLOSED, EXITED, etc.)
    
    Returns:
        Formatted status string with emoji
    """
    status_map = {
        'OPEN': '🟢 OPEN',
        'CLOSED': '🔴 CLOSED',
        'EXITED': '⚪ EXITED',
        'EXPIRED': '⚫ EXPIRED',
        'STOPPED': '⛔ STOPPED',
    }
    
    return status_map.get(status.upper(), status.upper())


def format_strategy(strategy: str) -> str:
    """
    Format strategy name for display.
    
    Args:
        strategy: Strategy name (e.g., "BULL_PUT", "BEAR_CALL")
    
    Returns:
        Formatted strategy string (e.g., "Bull Put", "Bear Call")
    """
    return strategy.replace('_', ' ').title()


def format_trade_summary(trade: dict) -> str:
    """
    Format complete trade summary string.
    
    Args:
        trade: Trade dictionary
    
    Returns:
        Formatted trade summary (e.g., "NIFTY Bull Put 21500/21000")
    """
    try:
        symbol = trade.get('symbol', 'N/A')
        strategy = format_strategy(trade.get('strategy', ''))
        short_strike = format_strike(trade.get('short_strike', 0))
        long_strike = format_strike(trade.get('long_strike', 0))
        
        return f"{symbol} {strategy} {short_strike}/{long_strike}"
    except (KeyError, TypeError):
        return "N/A"


# =============================================================================
# Miscellaneous Formatting
# =============================================================================

def format_order_type(order_type: str) -> str:
    """
    Format order type for display.
    
    Args:
        order_type: Order type (MARKET, LIMIT, etc.)
    
    Returns:
        Formatted order type string
    """
    return order_type.upper()


def format_order_status(order_status: str) -> str:
    """
    Format order status with appropriate styling.
    
    Args:
        order_status: Order status (COMPLETE, PENDING, REJECTED, etc.)
    
    Returns:
        Formatted status string
    """
    status_map = {
        'COMPLETE': '✅ COMPLETE',
        'PENDING': '⏳ PENDING',
        'REJECTED': '❌ REJECTED',
        'CANCELLED': '🚫 CANCELLED',
        'TRIGGER_PENDING': '⚠️ TRIGGER PENDING',
    }
    
    return status_map.get(order_status.upper(), order_status.upper())


def format_bot_status(status: str) -> str:
    """
    Format bot status for display.
    
    Args:
        status: Bot status (RUNNING, STOPPED, PAUSED)
    
    Returns:
        Formatted status string with emoji
    """
    status_map = {
        'RUNNING': '🟢 RUNNING',
        'STOPPED': '🔴 STOPPED',
        'PAUSED': '🟡 PAUSED',
        'ERROR': '⚠️ ERROR',
    }
    
    return status_map.get(status.upper(), status.upper())


def truncate_string(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """
    Truncate string to maximum length.
    
    Args:
        text: String to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
    
    Returns:
        Truncated string
    """
    if not isinstance(text, str):
        text = str(text)
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix
