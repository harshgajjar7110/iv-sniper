"""
Symbol Utilities - Centralized functions for option symbol parsing and reconstruction.

This module provides utility functions to:
- Parse Zerodha option symbols into components
- Reconstruct option symbols from components
- Calculate expiry dates
- Format trading symbols for Kite API

Usage:
    from ui.utils.symbol_utils import (
        parse_zerodha_symbol,
        reconstruct_option_symbol,
        get_option_symbols_for_trade,
    )
"""

import logging
import re
from datetime import date, datetime
from typing import Optional
from calendar import monthrange

logger = logging.getLogger(__name__)


# Month code mapping
MONTH_MAP = {
    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4,
    'MAY': 5, 'JUN': 6, 'JUL': 7, 'AUG': 8,
    'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
}

# Reverse month mapping
MONTH_CODES = {v: k for k, v in MONTH_MAP.items()}


def parse_zerodha_symbol(tradingsymbol: str, exchange: str = "NFO") -> dict:
    """
    Parse Zerodha option symbol to extract components.
    
    Example: NIFTY24FEB21500CE -> {
        symbol: NIFTY, 
        year: 2024, 
        month: FEB, 
        strike: 21500, 
        type: CE,
        expiry: 2024-02-29
    }
    
    Args:
        tradingsymbol: The trading symbol string (with or without exchange prefix)
        exchange: The exchange (default: NFO)
    
    Returns:
        Dictionary with parsed components
    """
    # Remove exchange prefix if present
    if ':' in tradingsymbol:
        tradingsymbol = tradingsymbol.split(':')[1]
    
    # Pattern for Zerodha option symbols: SYMBOLYYMONTHSTRIKETYPE
    pattern = r'^([A-Z]+)(\d{2})([A-Z]+)(\d+)((?:CE|PE))$'
    match = re.match(pattern, tradingsymbol.upper())
    
    if match:
        symbol = match.group(1)
        year = int('20' + match.group(2))
        month = match.group(3)
        strike = int(match.group(4))
        option_type = match.group(5)
        
        month_num = MONTH_MAP.get(month, 1)
        
        # Calculate expiry (last Thursday of the month)
        expiry = calculate_expiry_date(year, month_num)
        
        return {
            'symbol': symbol,
            'year': year,
            'month': month,
            'strike': strike,
            'option_type': option_type,
            'expiry': expiry.isoformat(),
            'strategy': 'BULL_PUT' if option_type == 'PE' else 'BEAR_CALL',
        }
    
    # Return empty parse result for invalid symbols
    return {
        'symbol': tradingsymbol,
        'year': 0,
        'month': '',
        'strike': 0,
        'option_type': '',
        'expiry': '',
        'strategy': 'UNKNOWN',
    }


def calculate_expiry_date(year: int, month: int) -> date:
    """
    Calculate the expiry date (last Thursday of the month) for a given month.
    
    Args:
        year: Year (e.g., 2024)
        month: Month number (1-12)
    
    Returns:
        Date object representing the last Thursday of the month
    """
    try:
        last_day = monthrange(year, month)[1]
        expiry = date(year, month, last_day)
        
        # Find last Thursday (weekday 3)
        for d in range(last_day, 0, -1):
            if date(year, month, d).weekday() == 3:
                expiry = date(year, month, d)
                break
        
        return expiry
    except (ValueError, TypeError) as e:
        logger.warning(f"Failed to calculate expiry for {year}-{month}: {e}")
        return date.today()


def reconstruct_option_symbol(
    symbol: str,
    expiry: str,
    strike: int,
    strategy: str,
    include_exchange: bool = True
) -> str:
    """
    Reconstruct Zerodha option trading symbol from components.
    
    Args:
        symbol: Underlying symbol (e.g., 'NIFTY', 'RELIANCE')
        expiry: Expiry date in YYYY-MM-DD format
        strike: Strike price
        strategy: Strategy type ('BULL_PUT' or 'BEAR_CALL')
        include_exchange: Whether to prefix with 'NFO:' (default: True)
    
    Returns:
        Trading symbol (e.g., 'NFO:NIFTY24FEB21500CE')
    
    Raises:
        ValueError: If expiry format is invalid
    
    Example:
        >>> reconstruct_option_symbol('NIFTY', '2024-02-29', 21500, 'BULL_PUT')
        'NFO:NIFTY24FEB21500CE'
    """
    try:
        exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid expiry format '{expiry}': {e}")
        raise ValueError(f"Invalid expiry format: {expiry}. Expected YYYY-MM-DD")
    
    yy = str(exp_date.year)[-2:]
    mon = MONTH_CODES.get(exp_date.month, 'JAN')
    leg_type = "PE" if "PUT" in strategy else "CE"
    
    trading_symbol = f"{symbol}{yy}{mon}{int(strike)}{leg_type}"
    
    if include_exchange:
        return f"NFO:{trading_symbol}"
    return trading_symbol


def get_option_symbols_for_trade(
    symbol: str,
    expiry: str,
    short_strike: int,
    long_strike: int,
    strategy: str
) -> tuple[str, str]:
    """
    Get the trading symbols for both legs of a spread trade.
    
    Args:
        symbol: Underlying symbol (e.g., 'NIFTY')
        expiry: Expiry date in YYYY-MM-DD format
        short_strike: Short leg strike price
        long_strike: Long leg strike price
        strategy: Strategy type ('BULL_PUT' or 'BEAR_CALL')
    
    Returns:
        Tuple of (short_symbol, long_symbol) with 'NFO:' prefix
    
    Example:
        >>> get_option_symbols_for_trade('NIFTY', '2024-02-29', 21500, 21000, 'BULL_PUT')
        ('NFO:NIFTY24FEB21500PE', 'NFO:NIFTY24FEB21000PE')
    """
    short_symbol = reconstruct_option_symbol(
        symbol=symbol,
        expiry=expiry,
        strike=short_strike,
        strategy=strategy,
        include_exchange=True
    )
    
    long_symbol = reconstruct_option_symbol(
        symbol=symbol,
        expiry=expiry,
        strike=long_strike,
        strategy=strategy,
        include_exchange=True
    )
    
    return short_symbol, long_symbol


def get_all_trade_symbols(trades: list[dict]) -> list[str]:
    """
    Get all option symbols from a list of trades.
    
    Args:
        trades: List of trade dictionaries from database
    
    Returns:
        List of all trading symbols with 'NFO:' prefix
    
    Example:
        >>> trades = [{'symbol': 'NIFTY', 'expiry': '2024-02-29', 
        ...            'short_strike': 21500, 'long_strike': 21000, 
        ...            'strategy': 'BULL_PUT'}]
        >>> get_all_trade_symbols(trades)
        ['NFO:NIFTY24FEB21500PE', 'NFO:NIFTY24FEB21000PE']
    """
    all_symbols = []
    
    for trade in trades:
        try:
            short_sym, long_sym = get_option_symbols_for_trade(
                symbol=trade['symbol'],
                expiry=trade['expiry'],
                short_strike=int(trade['short_strike']),
                long_strike=int(trade['long_strike']),
                strategy=trade['strategy']
            )
            all_symbols.extend([short_sym, long_sym])
        except (KeyError, ValueError) as e:
            logger.warning(f"Failed to get symbols for trade {trade.get('trade_id', 'unknown')}: {e}")
            continue
    
    return all_symbols


def get_trade_symbols_dict(trades: list[dict]) -> dict:
    """
    Get a mapping of trade_id to symbols for a list of trades.
    
    Args:
        trades: List of trade dictionaries from database
    
    Returns:
        Dictionary mapping trade_id to {'short': symbol, 'long': symbol}
    """
    trade_symbols = {}
    
    for trade in trades:
        trade_id = trade.get('trade_id')
        if not trade_id:
            continue
            
        try:
            short_sym, long_sym = get_option_symbols_for_trade(
                symbol=trade['symbol'],
                expiry=trade['expiry'],
                short_strike=int(trade['short_strike']),
                long_strike=int(trade['long_strike']),
                strategy=trade['strategy']
            )
            trade_symbols[trade_id] = {'short': short_sym, 'long': long_sym}
        except (KeyError, ValueError) as e:
            logger.warning(f"Failed to get symbols for trade {trade_id}: {e}")
            continue
    
    return trade_symbols
