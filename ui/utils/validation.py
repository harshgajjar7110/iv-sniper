"""
Validation Utility Module

Provides centralized validation functions for:
- Symbol validation
- Strike price validation
- Quantity validation
- Premium validation
- Date/Expiry validation
- Trade data validation
- Configuration validation
"""

import logging
from datetime import datetime, date
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)


# =============================================================================
# Symbol Validation
# =============================================================================

def validate_symbol(symbol: str) -> bool:
    """
    Validate stock/option symbol format.
    
    Args:
        symbol: Symbol to validate (e.g., 'NIFTY', 'RELIANCE')
    
    Returns:
        True if valid, False otherwise
    """
    if not symbol or not isinstance(symbol, str):
        logger.warning(f"Invalid symbol: {symbol} - must be a non-empty string")
        return False
    
    symbol = symbol.strip().upper()
    
    # Check for valid characters (alphanumeric only)
    if not symbol.isalnum():
        logger.warning(f"Invalid symbol: {symbol} - contains non-alphanumeric characters")
        return False
    
    # Check length constraints
    if len(symbol) < 1 or len(symbol) > 20:
        logger.warning(f"Invalid symbol: {symbol} - length must be between 1 and 20")
        return False
    
    return True


def validate_option_symbol(symbol: str) -> bool:
    """
    Validate option trading symbol format (e.g., 'NFO:NIFTY24FEB21500CE').
    
    Args:
        symbol: Full option trading symbol to validate
    
    Returns:
        True if valid, False otherwise
    """
    if not symbol or not isinstance(symbol, str):
        return False
    
    # Remove exchange prefix if present
    if ':' in symbol:
        parts = symbol.split(':')
        if len(parts) != 2:
            return False
        symbol = parts[1]
    
    # Basic format check: SYMBOLYYMONSTRIKETYPE (e.g., NIFTY24FEB21500CE)
    if len(symbol) < 10:
        return False
    
    # Last 2 characters should be CE or PE
    if symbol[-2:] not in ('CE', 'PE'):
        return False
    
    return True


# =============================================================================
# Strike Price Validation
# =============================================================================

def validate_strike_price(strike: Any, min_strike: int = 0, max_strike: int = 100000) -> bool:
    """
    Validate strike price value.
    
    Args:
        strike: Strike price to validate
        min_strike: Minimum allowed strike price (default: 0)
        max_strike: Maximum allowed strike price (default: 100000)
    
    Returns:
        True if valid, False otherwise
    """
    try:
        strike_value = int(strike)
        
        if strike_value < min_strike:
            logger.warning(f"Strike price {strike_value} below minimum {min_strike}")
            return False
        
        if strike_value > max_strike:
            logger.warning(f"Strike price {strike_value} above maximum {max_strike}")
            return False
        
        return True
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid strike price '{strike}': {e}")
        return False


def validate_spread_strikes(short_strike: Any, long_strike: Any, strategy: str) -> bool:
    """
    Validate spread strike prices (short should be closer to ATM than long).
    
    Args:
        short_strike: Short leg strike price
        long_strike: Long leg strike price
        strategy: Strategy type ('BULL_PUT' or 'BEAR_CALL')
    
    Returns:
        True if valid spread, False otherwise
    """
    try:
        short = int(short_strike)
        long = int(long_strike)
        
        if strategy == 'BULL_PUT':
            # For Bull Put: short strike > long strike (credit spread)
            if short <= long:
                logger.warning(f"Bull Put: short_strike ({short}) must be > long_strike ({long})")
                return False
        elif strategy == 'BEAR_CALL':
            # For Bear Call: short strike < long strike (credit spread)
            if short >= long:
                logger.warning(f"Bear Call: short_strike ({short}) must be < long_strike ({long})")
                return False
        else:
            logger.warning(f"Unknown strategy: {strategy}")
            return False
        
        return True
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid spread strikes: {e}")
        return False


# =============================================================================
# Quantity Validation
# =============================================================================

def validate_quantity(quantity: Any, min_qty: int = 1, max_qty: int = 10000) -> bool:
    """
    Validate order quantity.
    
    Args:
        quantity: Quantity to validate
        min_qty: Minimum allowed quantity (default: 1)
        max_qty: Maximum allowed quantity (default: 10000)
    
    Returns:
        True if valid, False otherwise
    """
    try:
        qty = int(quantity)
        
        if qty < min_qty:
            logger.warning(f"Quantity {qty} below minimum {min_qty}")
            return False
        
        if qty > max_qty:
            logger.warning(f"Quantity {qty} above maximum {max_qty}")
            return False
        
        return True
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid quantity '{quantity}': {e}")
        return False


def validate_lot_size(quantity: int, lot_size: int = 75) -> bool:
    """
    Validate quantity is a multiple of lot size (NSE F&O requirement).
    
    Args:
        quantity: Order quantity
        lot_size: Required lot size (default: 75 for NIFTY)
    
    Returns:
        True if valid lot size, False otherwise
    """
    try:
        qty = int(quantity)
        lot = int(lot_size)
        
        if qty % lot != 0:
            logger.warning(f"Quantity {qty} not a multiple of lot size {lot}")
            return False
        
        return True
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid lot size validation: {e}")
        return False


# =============================================================================
# Premium Validation
# =============================================================================

def validate_premium(premium: Any, min_premium: float = 0.0, max_premium: float = 10000.0) -> bool:
    """
    Validate premium value.
    
    Args:
        premium: Premium value to validate
        min_premium: Minimum allowed premium (default: 0)
        max_premium: Maximum allowed premium (default: 10000)
    
    Returns:
        True if valid, False otherwise
    """
    try:
        premium_value = float(premium)
        
        if premium_value < min_premium:
            logger.warning(f"Premium {premium_value} below minimum {min_premium}")
            return False
        
        if premium_value > max_premium:
            logger.warning(f"Premium {premium_value} above maximum {max_premium}")
            return False
        
        return True
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid premium '{premium}': {e}")
        return False


def validate_spread_credit(credit: Any) -> bool:
    """
    Validate spread credit (must be positive for credit spreads).
    
    Args:
        credit: Net credit received
    
    Returns:
        True if valid (positive), False otherwise
    """
    try:
        credit_value = float(credit)
        
        if credit_value <= 0:
            logger.warning(f"Spread credit must be positive, got {credit_value}")
            return False
        
        return True
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid spread credit '{credit}': {e}")
        return False


# =============================================================================
# Date/Expiry Validation
# =============================================================================

def validate_expiry_date(expiry: Union[str, date, datetime], 
                          min_days: int = 0, 
                          max_days: int = 365) -> bool:
    """
    Validate expiry date is within acceptable range.
    
    Args:
        expiry: Expiry date (string, date, or datetime object)
        min_days: Minimum days from now (default: 0)
        max_days: Maximum days from now (default: 365)
    
    Returns:
        True if valid, False otherwise
    """
    try:
        # Convert to date object
        if isinstance(expiry, str):
            expiry_date = datetime.fromisoformat(expiry).date()
        elif isinstance(expiry, datetime):
            expiry_date = expiry.date()
        elif isinstance(expiry, date):
            expiry_date = expiry
        else:
            logger.warning(f"Invalid expiry type: {type(expiry)}")
            return False
        
        today = date.today()
        days_until = (expiry_date - today).days
        
        if days_until < min_days:
            logger.warning(f"Expiry {expiry_date} is less than {min_days} days away")
            return False
        
        if days_until > max_days:
            logger.warning(f"Expiry {expiry_date} is more than {max_days} days away")
            return False
        
        return True
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid expiry date '{expiry}': {e}")
        return False


def validate_expiry_is_thursday(expiry: Union[str, date, datetime]) -> bool:
    """
    Validate that expiry date is a Thursday (standard NSE expiry day).
    
    Args:
        expiry: Expiry date to validate
    
    Returns:
        True if Thursday, False otherwise
    """
    try:
        # Convert to date object
        if isinstance(expiry, str):
            expiry_date = datetime.fromisoformat(expiry).date()
        elif isinstance(expiry, datetime):
            expiry_date = expiry.date()
        elif isinstance(expiry, date):
            expiry_date = expiry
        else:
            return False
        
        # Thursday is weekday() == 3
        if expiry_date.weekday() != 3:
            logger.warning(f"Expiry {expiry_date} is not a Thursday (weekday: {expiry_date.weekday()})")
            return False
        
        return True
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid expiry date '{expiry}': {e}")
        return False


# =============================================================================
# Trade Data Validation
# =============================================================================

def validate_trade_data(trade: dict) -> tuple[bool, Optional[str]]:
    """
    Validate complete trade data structure.
    
    Args:
        trade: Trade dictionary to validate
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    required_fields = ['symbol', 'short_strike', 'long_strike', 'strategy', 'expiry']
    
    # Check required fields
    for field in required_fields:
        if field not in trade or trade[field] is None:
            return False, f"Missing required field: {field}"
    
    # Validate symbol
    if not validate_symbol(trade['symbol']):
        return False, f"Invalid symbol: {trade['symbol']}"
    
    # Validate strategy
    if trade['strategy'] not in ('BULL_PUT', 'BEAR_CALL'):
        return False, f"Invalid strategy: {trade['strategy']}"
    
    # Validate strikes
    if not validate_strike_price(trade['short_strike']):
        return False, f"Invalid short_strike: {trade['short_strike']}"
    
    if not validate_strike_price(trade['long_strike']):
        return False, f"Invalid long_strike: {trade['long_strike']}"
    
    # Validate spread strikes
    if not validate_spread_strikes(trade['short_strike'], trade['long_strike'], trade['strategy']):
        return False, "Invalid spread: short/long strike relationship invalid for strategy"
    
    # Validate expiry
    if not validate_expiry_date(trade['expiry'], min_days=1, max_days=60):
        return False, f"Invalid expiry: {trade['expiry']}"
    
    return True, None


def validate_spread_data(spread: dict) -> tuple[bool, Optional[str]]:
    """
    Validate spread analysis data structure.
    
    Args:
        spread: Spread dictionary to validate
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check required fields
    required_fields = ['short_symbol', 'long_symbol', 'short_strike', 'long_strike', 
                       'strategy', 'net_credit', 'max_profit', 'max_loss']
    
    for field in required_fields:
        if field not in spread or spread[field] is None:
            return False, f"Missing required field: {field}"
    
    # Validate symbols
    if not validate_option_symbol(spread['short_symbol']):
        return False, f"Invalid short_symbol: {spread['short_symbol']}"
    
    if not validate_option_symbol(spread['long_symbol']):
        return False, f"Invalid long_symbol: {spread['long_symbol']}"
    
    # Validate credits
    if not validate_spread_credit(spread['net_credit']):
        return False, f"Invalid net_credit: {spread['net_credit']}"
    
    # Validate P&L
    if not validate_premium(spread['max_profit'], min_premium=0):
        return False, f"Invalid max_profit: {spread['max_profit']}"
    
    if spread['max_loss'] is not None:
        if not validate_premium(spread['max_loss'], min_premium=0):
            return False, f"Invalid max_loss: {spread['max_loss']}"
    
    # Validate risk-reward if present
    if 'risk_reward' in spread and spread['risk_reward'] is not None:
        try:
            rr = float(spread['risk_reward'])
            if rr <= 0:
                return False, f"Invalid risk_reward: {rr} (must be positive)"
        except (ValueError, TypeError):
            return False, f"Invalid risk_reward type: {type(spread['risk_reward'])}"
    
    return True, None


# =============================================================================
# Configuration Validation
# =============================================================================

def validate_capital_config(total_capital: Any, min_capital: float = 10000) -> bool:
    """
    Validate capital configuration.
    
    Args:
        total_capital: Total capital amount
        min_capital: Minimum allowed capital (default: 10000)
    
    Returns:
        True if valid, False otherwise
    """
    try:
        capital = float(total_capital)
        
        if capital < min_capital:
            logger.warning(f"Total capital {capital} below minimum {min_capital}")
            return False
        
        if capital > 100000000:  # 10 Crore max
            logger.warning(f"Total capital {capital} exceeds maximum")
            return False
        
        return True
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid capital value '{total_capital}': {e}")
        return False


def validate_risk_config(max_loss: Any, max_position_size: Any) -> tuple[bool, Optional[str]]:
    """
    Validate risk management configuration.
    
    Args:
        max_loss: Maximum loss per trade
        max_position_size: Maximum position size as percentage or amount
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Validate max loss
        max_loss_value = float(max_loss)
        if max_loss_value <= 0:
            return False, "max_loss must be positive"
        
        # Validate max position size
        max_pos = float(max_position_size)
        if max_pos <= 0 or max_pos > 100:
            return False, "max_position_size should be between 0 and 100 (percentage)"
        
        return True, None
    except (ValueError, TypeError) as e:
        return False, f"Invalid risk config: {e}"


def validate_scanner_config(min_iv_score: Any, min_volume: Any) -> tuple[bool, Optional[str]]:
    """
    Validate scanner configuration.
    
    Args:
        min_iv_score: Minimum IV score threshold
        min_volume: Minimum volume threshold
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Validate IV score
        iv_score = float(min_iv_score)
        if iv_score < 0 or iv_score > 100:
            return False, "min_iv_score should be between 0 and 100"
        
        # Validate volume
        volume = int(min_volume)
        if volume < 0:
            return False, "min_volume cannot be negative"
        
        return True, None
    except (ValueError, TypeError) as e:
        return False, f"Invalid scanner config: {e}"


# =============================================================================
# Numeric Range Validation
# =============================================================================

def validate_positive_number(value: Any, allow_zero: bool = False) -> bool:
    """
    Validate that a value is a positive number.
    
    Args:
        value: Value to validate
        allow_zero: Whether to allow zero (default: False)
    
    Returns:
        True if valid positive number, False otherwise
    """
    try:
        num = float(value)
        
        if allow_zero:
            return num >= 0
        else:
            return num > 0
    except (ValueError, TypeError):
        return False


def validate_percentage(value: Any, allow_zero: bool = True) -> bool:
    """
    Validate that a value is a valid percentage (0-100).
    
    Args:
        value: Value to validate
        allow_zero: Whether to allow zero (default: True)
    
    Returns:
        True if valid percentage, False otherwise
    """
    try:
        pct = float(value)
        
        if pct < 0 or pct > 100:
            return False
        
        if not allow_zero and pct == 0:
            return False
        
        return True
    except (ValueError, TypeError):
        return False


def validate_range(value: Any, min_val: float, max_val: float) -> bool:
    """
    Validate that a value is within a specified range.
    
    Args:
        value: Value to validate
        min_val: Minimum value (inclusive)
        max_val: Maximum value (inclusive)
    
    Returns:
        True if within range, False otherwise
    """
    try:
        num = float(value)
        return min_val <= num <= max_val
    except (ValueError, TypeError):
        return False
