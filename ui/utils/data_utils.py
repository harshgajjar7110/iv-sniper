"""
UI Data Utilities - Common data fetching functions for the IV-Sniper UI.

This module provides utility functions to fetch and process data from:
- SQLite database (trade_log, iv_history)
- Kite Connect API (margins, positions, quotes)
"""

import logging
from datetime import datetime, date
from typing import Any
from collections import defaultdict

from db.connection import get_connection
from core.kite_client import KiteClient

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Database Queries
# ──────────────────────────────────────────────

def get_open_trades() -> list[dict]:
    """Get all open trades from the database."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM trade_log WHERE status = 'OPEN' ORDER BY entry_time DESC"
        )
        return [dict(row) for row in cursor.fetchall()]


def get_today_trades() -> list[dict]:
    """Get all trades entered today."""
    today = date.today().isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            """SELECT * FROM trade_log 
               WHERE date(entry_time) = ? 
               ORDER BY entry_time DESC""",
            (today,)
        )
        return [dict(row) for row in cursor.fetchall()]


def get_closed_trades(days: int = 30) -> list[dict]:
    """Get closed trades for the last N days."""
    with get_connection() as conn:
        cursor = conn.execute(
            """SELECT * FROM trade_log 
               WHERE status = 'CLOSED' 
               AND exit_time IS NOT NULL
               ORDER BY exit_time DESC 
               LIMIT ?""",
            (days,)
        )
        return [dict(row) for row in cursor.fetchall()]


def get_trade_statistics() -> dict:
    """Calculate trade statistics (P&L, win rate, etc.)."""
    with get_connection() as conn:
        # Today's P&L
        today = date.today().isoformat()
        cursor = conn.execute(
            """SELECT SUM(pnl) as total_pnl, COUNT(*) as trade_count
               FROM trade_log 
               WHERE status = 'CLOSED' 
               AND date(exit_time) = ?""",
            (today,)
        )
        today_stats = dict(cursor.fetchone()) or {'total_pnl': 0, 'trade_count': 0}
        
        # Month-to-date P&L
        cursor = conn.execute(
            """SELECT strftime('%Y-%m', exit_time) as month, 
                      SUM(pnl) as total_pnl, 
                      COUNT(*) as trade_count,
                      SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins
               FROM trade_log 
               WHERE status = 'CLOSED' 
               AND exit_time IS NOT NULL
               AND strftime('%Y-%m', exit_time) = strftime('%Y-%m', 'now')
               GROUP BY month"""
        )
        mtd_row = cursor.fetchone()
        
        # All time stats
        cursor = conn.execute(
            """SELECT SUM(pnl) as total_pnl, 
                      COUNT(*) as trade_count,
                      SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins
               FROM trade_log 
               WHERE status = 'CLOSED'"""
        )
        all_time = dict(cursor.fetchone()) or {
            'total_pnl': 0, 'trade_count': 0, 'wins': 0
        }
        
        return {
            'today_pnl': today_stats.get('total_pnl', 0) or 0,
            'today_trades': today_stats.get('trade_count', 0) or 0,
            'mtd_pnl': mtd_row['total_pnl'] if mtd_row else 0,
            'mtd_trades': mtd_row['trade_count'] if mtd_row else 0,
            'mtd_wins': mtd_row['wins'] if mtd_row else 0,
            'all_time_pnl': all_time.get('total_pnl', 0) or 0,
            'all_time_trades': all_time.get('trade_count', 0) or 0,
            'all_time_wins': all_time.get('wins', 0) or 0,
        }


def get_capital_info() -> dict:
    """Get capital information from config and database."""
    # This is a simplified version - in production, you'd fetch from Kite
    return {
        'total_capital': 1_000_000,  # ₹10 lakhs (configurable)
        'used_margin': 0,  # Would be fetched from Kite
        'available': 1_000_000,  # Would be calculated from Kite
    }


# ──────────────────────────────────────────────
# Kite API Functions
# ──────────────────────────────────────────────

def get_account_margins(kite: KiteClient) -> dict:
    """Fetch account margins from Kite."""
    try:
        margins = kite.margins()
        return {
            'total': margins.get('total', {}).get('available_balance', 0),
            'used': margins.get('total', {}).get('used_balance', 0),
            'available': margins.get('total', {}).get('available_balance', 0),
        }
    except Exception as e:
        logger.error(f"Failed to fetch margins: {e}")
        return {'total': 0, 'used': 0, 'available': 0}


def get_detailed_margins(kite: KiteClient) -> dict:
    """Fetch detailed margin breakdown from Kite (equity + commodity)."""
    try:
        margins = kite.margins()
        
        # Equity margins
        equity = margins.get('equity', {})
        # Commodity margins
        commodity = margins.get('commodity', {})
        
        return {
            'equity': {
                'total': equity.get('total', 0),
                'available': equity.get('available_balance', 0),
                'used': equity.get('used_balance', 0),
                'blocked': equity.get('blocked', 0),
            },
            'commodity': {
                'total': commodity.get('total', 0),
                'available': commodity.get('available_balance', 0),
                'used': commodity.get('used_balance', 0),
                'blocked': commodity.get('blocked', 0),
            },
            'total_available': (
                equity.get('available_balance', 0) + 
                commodity.get('available_balance', 0)
            ),
            'total_used': (
                equity.get('used_balance', 0) + 
                commodity.get('used_balance', 0)
            ),
        }
    except Exception as e:
        logger.error(f"Failed to fetch detailed margins: {e}")
        return {
            'equity': {'total': 0, 'available': 0, 'used': 0, 'blocked': 0},
            'commodity': {'total': 0, 'available': 0, 'used': 0, 'blocked': 0},
            'total_available': 0,
            'total_used': 0,
        }


def parse_zerodha_symbol(tradingsymbol: str, exchange: str = "NFO") -> dict:
    """
    Parse Zerodha option symbol to extract components.
    
    Example: NIFTY24FEB21500CE -> {symbol: NIFTY, year: 2024, month: FEB, strike: 21500, type: CE}
    """
    import re
    from calendar import monthrange
    
    # Remove exchange prefix if present
    if ':' in tradingsymbol:
        tradingsymbol = tradingsymbol.split(':')[1]
    
    # Pattern for Zerodha option symbols: SYMBOLYYMONTHSTRIKETYPE
    # e.g., NIFTY24FEB21500CE
    pattern = r'^([A-Z]+)(\d{2})([A-Z]+)(\d+)((?:CE|PE))$'
    match = re.match(pattern, tradingsymbol.upper())
    
    if match:
        symbol = match.group(1)
        year = int('20' + match.group(2))  # Convert YY to YYYY
        month = match.group(3)
        strike = int(match.group(4))
        option_type = match.group(5)
        
        # Map month to number
        month_map = {
            'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4,
            'MAY': 5, 'JUN': 6, 'JUL': 7, 'AUG': 8,
            'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
        }
        month_num = month_map.get(month, 1)
        
        # Format expiry date (last Thursday of the month)
        try:
            last_day = monthrange(year, month_num)[1]
            # Find last Thursday (weekday 3)
            for d in range(last_day, 0, -1):
                if date(year, month_num, d).weekday() == 3:
                    expiry = date(year, month_num, d)
                    break
            else:
                expiry = date(year, month_num, last_day)
        except:
            expiry = date.today()
        
        return {
            'symbol': symbol,
            'year': year,
            'month': month,
            'strike': strike,
            'option_type': option_type,
            'expiry': expiry.isoformat(),
            'strategy': 'BULL_PUT' if option_type == 'PE' else 'BEAR_CALL',
        }
    
    return {
        'symbol': tradingsymbol,
        'year': 0,
        'month': '',
        'strike': 0,
        'option_type': '',
        'expiry': '',
        'strategy': 'UNKNOWN',
    }


def get_positions(kite: KiteClient) -> dict:
    """Fetch current positions from Kite."""
    try:
        return kite.positions()
    except Exception as e:
        logger.error(f"Failed to fetch positions: {e}")
        return {'net': [], 'day': []}


def get_quote(kite: KiteClient, symbol: str) -> dict:
    """Fetch quote for a specific symbol."""
    try:
        quotes = kite.quote([symbol])
        return quotes.get(symbol, {})
    except Exception as e:
        logger.error(f"Failed to fetch quote for {symbol}: {e}")
        return {}


def get_quotes(kite: KiteClient, symbols: list[str]) -> dict:
    """Fetch quotes for multiple symbols."""
    try:
        return kite.quote(symbols)
    except Exception as e:
        logger.error(f"Failed to fetch quotes: {e}")
        return {}


def get_live_positions(kite: KiteClient) -> list[dict]:
    """
    Fetch live positions from Zerodha and format them for display.
    
    Returns:
    --------
    list[dict]
        List of spread dictionaries with combined position data
    """
    try:
        positions = kite.positions()
        
        all_positions = []
        
        # Process net positions (overnight + day)
        net_positions = positions.get('net', [])
        day_positions = positions.get('day', [])
        
        # Combine net and day positions
        all_pos_data = net_positions + day_positions
        
        for pos in all_pos_data:
            # Skip if no quantity
            if pos.get('quantity', 0) == 0:
                continue
            
            tradingsymbol = pos.get('tradingsymbol', '')
            exchange = pos.get('exchange', 'NFO')
            
            # Only process option positions from NFO
            if exchange != 'NFO' or not tradingsymbol:
                continue
            
            # Parse the symbol
            parsed = parse_zerodha_symbol(tradingsymbol, exchange)
            
            # Calculate P&L
            average_price = pos.get('average_price', 0)
            last_price = pos.get('last_price', 0)
            quantity = pos.get('quantity', 0)
            
            # M2M (Mark to Market) P&L
            m2m = pos.get('m2m', 0)
            realised_pnl = pos.get('realised_pnl', 0)
            unrealised_pnl = pos.get('unrealised_pnl', 0)
            
            # Determine position type
            is_short = quantity < 0  # Sold position
            
            position = {
                'tradingsymbol': tradingsymbol,
                'exchange': exchange,
                'symbol': parsed['symbol'],
                'strike': parsed['strike'],
                'option_type': parsed['option_type'],
                'expiry': parsed['expiry'],
                'strategy': parsed['strategy'],
                'quantity': abs(quantity),
                'is_short': is_short,
                'average_price': average_price,
                'last_price': last_price,
                'premium': average_price,
                'm2m': m2m,
                'realised_pnl': realised_pnl,
                'unrealised_pnl': unrealised_pnl,
                'buy_quantity': pos.get('buy_quantity', 0),
                'sell_quantity': pos.get('sell_quantity', 0),
                'pending_orders': pos.get('pending_orders', 0),
                'collateral': pos.get('collateral', 0),
                'value': pos.get('value', 0),
            }
            
            all_positions.append(position)
        
        # Group positions by underlying symbol and expiry to form spreads
        return group_positions_into_spreads(all_positions)
        
    except Exception as e:
        logger.error(f"Failed to fetch live positions: {e}")
        return []


def group_positions_into_spreads(positions: list[dict]) -> list[dict]:
    """
    Group individual option positions into spreads based on:
    - Same underlying symbol
    - Same expiry
    - Same strategy (PE for Bull Put, CE for Bear Call)
    """
    # Group by symbol + expiry + strategy
    groups = defaultdict(list)
    
    for pos in positions:
        key = f"{pos['symbol']}_{pos['expiry']}_{pos['strategy']}"
        groups[key].append(pos)
    
    spreads = []
    
    for key, group_positions in groups.items():
        if len(group_positions) < 2:
            # Single leg position - skip for now
            continue
        
        # Separate short and long legs
        short_legs = [p for p in group_positions if p['is_short']]
        long_legs = [p for p in group_positions if not p['is_short']]
        
        if not short_legs or not long_legs:
            continue
        
        # Take the first short and long leg (should be one each for simple spreads)
        short_leg = short_legs[0]
        long_leg = long_legs[0]
        
        # Calculate net premium (credit if short > long, debit if long > short)
        net_credit = short_leg['average_price'] - long_leg['average_price']
        current_debit = short_leg['last_price'] - long_leg['last_price']
        
        # Lot size is the minimum of both legs
        lot_size = min(short_leg['quantity'], long_leg['quantity'])
        
        # Calculate spread P&L
        # P&L = Entry Credit - Current Debit (for credit spreads)
        spread_pnl = (net_credit - current_debit) * lot_size
        
        # Percentage
        if net_credit > 0:
            spread_pnl_pct = ((net_credit - current_debit) / net_credit) * 100
        else:
            spread_pnl_pct = 0
        
        spread = {
            'spread_id': key,
            'symbol': short_leg['symbol'],
            'strategy': short_leg['strategy'],
            'expiry': short_leg['expiry'],
            'short_strike': short_leg['strike'],
            'long_strike': long_leg['strike'],
            'short_leg': short_leg,
            'long_leg': long_leg,
            'net_credit': net_credit,
            'current_debit': current_debit,
            # Combined P&L from both legs
            'm2m': short_leg['m2m'] + long_leg['m2m'],
            'realised_pnl': short_leg['realised_pnl'] + long_leg['realised_pnl'],
            'unrealised_pnl': short_leg['unrealised_pnl'] + long_leg['unrealised_pnl'],
            'lot_size': lot_size,
            'pnl': spread_pnl,
            'pnl_pct': spread_pnl_pct,
        }
        
        spreads.append(spread)
    
    return spreads


# ──────────────────────────────────────────────
# Trade Execution Helpers
# ──────────────────────────────────────────────

def calculate_spread_pnl(trade: dict, current_prices: dict) -> dict:
    """
    Calculate current P&L for a spread trade.
    
    Parameters:
    -----------
    trade : dict
        Trade details from database
    current_prices : dict
        Current prices for short and long legs
    
    Returns:
    --------
    dict
        P&L details including current premium, P&L amount and percentage
    """
    # Reconstruct trading symbols
    try:
        exp_date = datetime.strptime(trade['expiry'], "%Y-%m-%d").date()
    except:
        exp_date = date.today()
    
    yy = str(exp_date.year)[-2:]
    mon = exp_date.strftime("%b").upper()
    leg_type = "PE" if "PUT" in trade['strategy'] else "CE"
    
    short_sym = f"NFO:{trade['symbol']}{yy}{mon}{int(trade['short_strike'])}{leg_type}"
    long_sym = f"NFO:{trade['symbol']}{yy}{mon}{int(trade['long_strike'])}{leg_type}"
    
    short_price = current_prices.get(short_sym, {}).get('last_price', 0)
    long_price = current_prices.get(long_sym, {}).get('last_price', 0)
    
    # Current spread debit (to close)
    current_debit = short_price - long_price
    entry_credit = trade['net_credit']
    
    # P&L = Entry Credit - Current Debit
    # If we sold at 25 and buy back at 12, profit = 13
    pnl = (entry_credit - current_debit) * trade['lot_size']
    
    # Percentage change
    if entry_credit > 0:
        pnl_pct = ((entry_credit - current_debit) / entry_credit) * 100
    else:
        pnl_pct = 0
    
    return {
        'current_debit': current_debit,
        'entry_credit': entry_credit,
        'pnl': pnl,
        'pnl_pct': pnl_pct,
        'short_price': short_price,
        'long_price': long_price,
    }


def get_exit_status(trade: dict, current_prices: dict) -> dict:
    """
    Check exit rule status for a trade.
    
    Returns:
    --------
    dict
        Status of each exit rule (target, SL, time stop)
    """
    import config
    
    pnl_data = calculate_spread_pnl(trade, current_prices)
    current_debit = pnl_data['current_debit']
    entry_credit = pnl_data['entry_credit']
    
    # Target: 50% profit (debit drops to 50% of credit)
    target_debit = entry_credit * (1 - config.SPREAD_TARGET_PCT / 100)
    target_hit = current_debit <= target_debit
    
    # Stop Loss: premium doubles (debit >= 2x credit)
    sl_debit = entry_credit * (1 + config.SPREAD_SL_PCT / 100)
    sl_hit = current_debit >= sl_debit
    
    # Time stop: Thursday 2:30 PM
    now = datetime.now()
    is_thursday = now.weekday() == 3
    is_expiry_time = now.time().hour >= 14 and now.time().minute >= 30
    time_stop_hit = is_thursday and is_expiry_time
    
    return {
        'target_hit': target_hit,
        'sl_hit': sl_hit,
        'time_stop_hit': time_stop_hit,
        'target_debit': target_debit,
        'sl_debit': sl_debit,
    }


def get_quotes(kite: KiteClient, symbols: list[str]) -> dict:
    """Fetch quotes for multiple symbols."""
    try:
        return kite.quote(symbols)
    except Exception as e:
        logger.error(f"Failed to fetch quotes: {e}")
        return {}


def get_live_positions(kite: KiteClient) -> list[dict]:
    """
    Fetch live positions from Zerodha and format them for display.
    
    Returns:
    --------
    list[dict]
        List of spread dictionaries with combined position data
    """
    try:
        positions = kite.positions()
        
        all_positions = []
        
        # Process net positions (overnight + day)
        net_positions = positions.get('net', [])
        day_positions = positions.get('day', [])
        
        # Combine net and day positions
        all_pos_data = net_positions + day_positions
        
        for pos in all_pos_data:
            # Skip if no quantity
            if pos.get('quantity', 0) == 0:
                continue
            
            tradingsymbol = pos.get('tradingsymbol', '')
            exchange = pos.get('exchange', 'NFO')
            
            # Only process option positions from NFO
            if exchange != 'NFO' or not tradingsymbol:
                continue
            
            # Parse the symbol
            parsed = parse_zerodha_symbol(tradingsymbol, exchange)
            
            # Calculate P&L
            average_price = pos.get('average_price', 0)
            last_price = pos.get('last_price', 0)
            quantity = pos.get('quantity', 0)
            
            # M2M (Mark to Market) P&L
            m2m = pos.get('m2m', 0)
            realised_pnl = pos.get('realised_pnl', 0)
            unrealised_pnl = pos.get('unrealised_pnl', 0)
            
            # Determine position type
            is_short = quantity < 0  # Sold position
            
            position = {
                'tradingsymbol': tradingsymbol,
                'exchange': exchange,
                'symbol': parsed['symbol'],
                'strike': parsed['strike'],
                'option_type': parsed['option_type'],
                'expiry': parsed['expiry'],
                'strategy': parsed['strategy'],
                'quantity': abs(quantity),
                'is_short': is_short,
                'average_price': average_price,
                'last_price': last_price,
                'premium': average_price,
                'm2m': m2m,
                'realised_pnl': realised_pnl,
                'unrealised_pnl': unrealised_pnl,
                'buy_quantity': pos.get('buy_quantity', 0),
                'sell_quantity': pos.get('sell_quantity', 0),
                'pending_orders': pos.get('pending_orders', 0),
                'collateral': pos.get('collateral', 0),
                'value': pos.get('value', 0),
            }
            
            all_positions.append(position)
        
        # Group positions by underlying symbol and expiry to form spreads
        return group_positions_into_spreads(all_positions)
        
    except Exception as e:
        logger.error(f"Failed to fetch live positions: {e}")
        return []


def group_positions_into_spreads(positions: list[dict]) -> list[dict]:
    """
    Group individual option positions into spreads based on:
    - Same underlying symbol
    - Same expiry
    - Same strategy (PE for Bull Put, CE for Bear Call)
    """
    # Group by symbol + expiry + strategy
    groups = defaultdict(list)
    
    for pos in positions:
        key = f"{pos['symbol']}_{pos['expiry']}_{pos['strategy']}"
        groups[key].append(pos)
    
    spreads = []
    
    for key, group_positions in groups.items():
        if len(group_positions) < 2:
            # Single leg position - skip for now
            continue
        
        # Separate short and long legs
        short_legs = [p for p in group_positions if p['is_short']]
        long_legs = [p for p in group_positions if not p['is_short']]
        
        if not short_legs or not long_legs:
            continue
        
        # Take the first short and long leg (should be one each for simple spreads)
        short_leg = short_legs[0]
        long_leg = long_legs[0]
        
        # Calculate net premium (credit if short > long, debit if long > short)
        net_credit = short_leg['average_price'] - long_leg['average_price']
        current_debit = short_leg['last_price'] - long_leg['last_price']
        
        # Lot size is the minimum of both legs
        lot_size = min(short_leg['quantity'], long_leg['quantity'])
        
        # Calculate spread P&L
        # P&L = Entry Credit - Current Debit (for credit spreads)
        spread_pnl = (net_credit - current_debit) * lot_size
        
        # Percentage
        if net_credit > 0:
            spread_pnl_pct = ((net_credit - current_debit) / net_credit) * 100
        else:
            spread_pnl_pct = 0
        
        spread = {
            'spread_id': key,
            'symbol': short_leg['symbol'],
            'strategy': short_leg['strategy'],
            'expiry': short_leg['expiry'],
            'short_strike': short_leg['strike'],
            'long_strike': long_leg['strike'],
            'short_leg': short_leg,
            'long_leg': long_leg,
            'net_credit': net_credit,
            'current_debit': current_debit,
            # Combined P&L from both legs
            'm2m': short_leg['m2m'] + long_leg['m2m'],
            'realised_pnl': short_leg['realised_pnl'] + long_leg['realised_pnl'],
            'unrealised_pnl': short_leg['unrealised_pnl'] + long_leg['unrealised_pnl'],
            'lot_size': lot_size,
            'pnl': spread_pnl,
            'pnl_pct': spread_pnl_pct,
        }
        
        spreads.append(spread)
    
    return spreads


# ──────────────────────────────────────────────
# Trade Execution Helpers
# ──────────────────────────────────────────────

def calculate_spread_pnl(trade: dict, current_prices: dict) -> dict:
    """
    Calculate current P&L for a spread trade.
    
    Parameters:
    -----------
    trade : dict
        Trade details from database
    current_prices : dict
        Current prices for short and long legs
    
    Returns:
    --------
    dict
        P&L details including current premium, P&L amount and percentage
    """
    # Reconstruct trading symbols
    try:
        exp_date = datetime.strptime(trade['expiry'], "%Y-%m-%d").date()
    except:
        exp_date = date.today()
    
    yy = str(exp_date.year)[-2:]
    mon = exp_date.strftime("%b").upper()
    leg_type = "PE" if "PUT" in trade['strategy'] else "CE"
    
    short_sym = f"NFO:{trade['symbol']}{yy}{mon}{int(trade['short_strike'])}{leg_type}"
    long_sym = f"NFO:{trade['symbol']}{yy}{mon}{int(trade['long_strike'])}{leg_type}"
    
    short_price = current_prices.get(short_sym, {}).get('last_price', 0)
    long_price = current_prices.get(long_sym, {}).get('last_price', 0)
    
    # Current spread debit (to close)
    current_debit = short_price - long_price
    entry_credit = trade['net_credit']
    
    # P&L = Entry Credit - Current Debit
    # If we sold at 25 and buy back at 12, profit = 13
    pnl = (entry_credit - current_debit) * trade['lot_size']
    
    # Percentage change
    if entry_credit > 0:
        pnl_pct = ((entry_credit - current_debit) / entry_credit) * 100
    else:
        pnl_pct = 0
    
    return {
        'current_debit': current_debit,
        'entry_credit': entry_credit,
        'pnl': pnl,
        'pnl_pct': pnl_pct,
        'short_price': short_price,
        'long_price': long_price,
    }


def get_exit_status(trade: dict, current_prices: dict) -> dict:
    """
    Check exit rule status for a trade.
    
    Returns:
    --------
    dict
        Status of each exit rule (target, SL, time stop)
    """
    import config
    
    pnl_data = calculate_spread_pnl(trade, current_prices)
    current_debit = pnl_data['current_debit']
    entry_credit = pnl_data['entry_credit']
    
    # Target: 50% profit (debit drops to 50% of credit)
    target_debit = entry_credit * (1 - config.SPREAD_TARGET_PCT / 100)
    target_hit = current_debit <= target_debit
    
    # Stop Loss: premium doubles (debit >= 2x credit)
    sl_debit = entry_credit * (1 + config.SPREAD_SL_PCT / 100)
    sl_hit = current_debit >= sl_debit
    
    # Time stop: Thursday 2:30 PM
    now = datetime.now()
    is_thursday = now.weekday() == 3
    is_expiry_time = now.time().hour >= 14 and now.time().minute >= 30
    time_stop_hit = is_thursday and is_expiry_time
    
    return {
        'target_hit': target_hit,
        'sl_hit': sl_hit,
        'time_stop_hit': time_stop_hit,
        'target_debit': target_debit,
        'sl_debit': sl_debit,
    }


def get_positions(kite: KiteClient) -> dict:
    """Fetch current positions from Kite."""
    try:
        return kite.positions()
    except Exception as e:
        logger.error(f"Failed to fetch positions: {e}")
        return {'net': [], 'day': []}


def get_quote(kite: KiteClient, symbol: str) -> dict:
    """Fetch quote for a specific symbol."""
    try:
        quotes = kite.quote([symbol])
        return quotes.get(symbol, {})
    except Exception as e:
        logger.error(f"Failed to fetch quote for {symbol}: {e}")
        return {}


def get_quotes(kite: KiteClient, symbols: list[str]) -> dict:
    """Fetch quotes for multiple symbols."""
    try:
        return kite.quote(symbols)
    except Exception as e:
        logger.error(f"Failed to fetch quotes: {e}")
        return {}


# ──────────────────────────────────────────────
# Trade Execution Helpers
# ──────────────────────────────────────────────

def calculate_spread_pnl(trade: dict, current_prices: dict) -> dict:
    """
    Calculate current P&L for a spread trade.
    
    Parameters:
    -----------
    trade : dict
        Trade details from database
    current_prices : dict
        Current prices for short and long legs
    
    Returns:
    --------
    dict
        P&L details including current premium, P&L amount and percentage
    """
    # Reconstruct trading symbols
    try:
        exp_date = datetime.strptime(trade['expiry'], "%Y-%m-%d").date()
    except:
        exp_date = date.today()
    
    yy = str(exp_date.year)[-2:]
    mon = exp_date.strftime("%b").upper()
    leg_type = "PE" if "PUT" in trade['strategy'] else "CE"
    
    short_sym = f"NFO:{trade['symbol']}{yy}{mon}{int(trade['short_strike'])}{leg_type}"
    long_sym = f"NFO:{trade['symbol']}{yy}{mon}{int(trade['long_strike'])}{leg_type}"
    
    short_price = current_prices.get(short_sym, {}).get('last_price', 0)
    long_price = current_prices.get(long_sym, {}).get('last_price', 0)
    
    # Current spread debit (to close)
    current_debit = short_price - long_price
    entry_credit = trade['net_credit']
    
    # P&L = Entry Credit - Current Debit
    # If we sold at 25 and buy back at 12, profit = 13
    pnl = (entry_credit - current_debit) * trade['lot_size']
    
    # Percentage change
    if entry_credit > 0:
        pnl_pct = ((entry_credit - current_debit) / entry_credit) * 100
    else:
        pnl_pct = 0
    
    return {
        'current_debit': current_debit,
        'entry_credit': entry_credit,
        'pnl': pnl,
        'pnl_pct': pnl_pct,
        'short_price': short_price,
        'long_price': long_price,
    }


def get_exit_status(trade: dict, current_prices: dict) -> dict:
    """
    Check exit rule status for a trade.
    
    Returns:
    --------
    dict
        Status of each exit rule (target, SL, time stop)
    """
    import config
    
    pnl_data = calculate_spread_pnl(trade, current_prices)
    current_debit = pnl_data['current_debit']
    entry_credit = pnl_data['entry_credit']
    
    # Target: 50% profit (debit drops to 50% of credit)
    target_debit = entry_credit * (1 - config.SPREAD_TARGET_PCT / 100)
    target_hit = current_debit <= target_debit
    
    # Stop Loss: premium doubles (debit >= 2x credit)
    sl_debit = entry_credit * (1 + config.SPREAD_SL_PCT / 100)
    sl_hit = current_debit >= sl_debit
    
    # Time stop: Thursday 2:30 PM
    now = datetime.now()
    is_thursday = now.weekday() == 3
    is_expiry_time = now.time().hour >= 14 and now.time().minute >= 30
    time_stop_hit = is_thursday and is_expiry_time
    
    return {
        'target_hit': target_hit,
        'sl_hit': sl_hit,
        'time_stop_hit': time_stop_hit,
        'target_debit': target_debit,
        'sl_debit': sl_debit,
    }
    # If we sold at 25 and buy back at 12, profit = 13
    pnl = (entry_credit - current_debit) * trade['lot_size']
    
    # Percentage change
    if entry_credit > 0:
        pnl_pct = ((entry_credit - current_debit) / entry_credit) * 100
    else:
        pnl_pct = 0
    
    return {
        'current_debit': current_debit,
        'entry_credit': entry_credit,
        'pnl': pnl,
        'pnl_pct': pnl_pct,
        'short_price': short_price,
        'long_price': long_price,
    }


def get_exit_status(trade: dict, current_prices: dict) -> dict:
    """
    Check exit rule status for a trade.
    
    Returns:
    --------
    dict
        Status of each exit rule (target, SL, time stop)
    """
    import config
    
    pnl_data = calculate_spread_pnl(trade, current_prices)
    current_debit = pnl_data['current_debit']
    entry_credit = pnl_data['entry_credit']
    
    # Target: 50% profit (debit drops to 50% of credit)
    target_debit = entry_credit * (1 - config.SPREAD_TARGET_PCT / 100)
    target_hit = current_debit <= target_debit
    
    # Stop Loss: premium doubles (debit >= 2x credit)
    sl_debit = entry_credit * (1 + config.SPREAD_SL_PCT / 100)
    sl_hit = current_debit >= sl_debit
    
    # Time stop: Thursday 2:30 PM
    now = datetime.now()
    is_thursday = now.weekday() == 3
    is_expiry_time = now.time().hour >= 14 and now.time().minute >= 30
    time_stop_hit = is_thursday and is_expiry_time
    
    return {
        'target_hit': target_hit,
        'sl_hit': sl_hit,
        'time_stop_hit': time_stop_hit,
        'target_debit': target_debit,
        'sl_debit': sl_debit,
    }

    match = re.match(pattern, tradingsymbol)
    
    if match:
        symbol = match.group(1)
        year = int('20' + match.group(2))  # Convert YY to YYYY
        month = match.group(3)
        strike = int(match.group(4))
        option_type = match.group(5)
        
        # Map month to number
        month_map = {
            'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4,
            'MAY': 5, 'JUN': 6, 'JUL': 7, 'AUG': 8,
            'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
        }
        month_num = month_map.get(month, 1)
        
        # Format expiry date
        try:
            expiry = date(year, month_num, 1)
            # Get last Thursday of the month ( Zerodha expiry)
            from calendar import monthrange
            last_day = monthrange(year, month_num)[1]
            # Find last Thursday (weekday 3)
            for d in range(last_day, 0, -1):
                if date(year, month_num, d).weekday() == 3:
                    expiry = date(year, month_num, d)
                    break
        except:
            expiry = date.today()
        
        return {
            'symbol': symbol,
            'year': year,
            'month': month,
            'strike': strike,
            'option_type': option_type,
            'expiry': expiry.isoformat(),
            'strategy': 'BULL_PUT' if option_type == 'PE' else 'BEAR_CALL',
        }
    
    return {
        'symbol': tradingsymbol,
        'year': 0,
        'month': '',
        'strike': 0,
        'option_type': '',
        'expiry': '',
        'strategy': 'UNKNOWN',
    }


def get_live_positions(kite: KiteClient) -> list[dict]:
    """
    Fetch live positions from Zerodha and format them for display.
    
    Returns:
    --------
    list[dict]
        List of position dictionaries with parsed option data
    """
    try:
        positions = kite.positions()
        
        all_positions = []
        
        # Process net positions (overnight + day)
        net_positions = positions.get('net', [])
        day_positions = positions.get('day', [])
        
        # Combine net and day positions
        all_pos_data = net_positions + day_positions
        
        for pos in all_pos_data:
            # Skip if no quantity
            if pos.get('quantity', 0) == 0:
                continue
            
            tradingsymbol = pos.get('tradingsymbol', '')
            exchange = pos.get('exchange', 'NFO')
            
            # Only process option positions from NFO
            if exchange != 'NFO' or not tradingsymbol:
                continue
            
            # Parse the symbol
            parsed = parse_zerodha_symbol(tradingsymbol, exchange)
            
            # Calculate P&L
            average_price = pos.get('average_price', 0)
            last_price = pos.get('last_price', 0)
            quantity = pos.get('quantity', 0)
            
            # For bought positions: P&L = (current - avg) * qty
            # For sold positions: P&L = (avg - current) * qty
            buy_quantity = pos.get('buy_quantity', 0)
            sell_quantity = pos.get('sell_quantity', 0)
            
            # M2M (Mark to Market) P&L
            m2m = pos.get('m2m', 0)
            realised_pnl = pos.get('realised_pnl', 0)
            unrealised_pnl = pos.get('unrealised_pnl', 0)
            
            # Calculate premium per unit
            if quantity != 0:
                premium = average_price
            else:
                premium = 0
            
            # Determine position type
            is_short = quantity < 0  # Sold position
            
            position = {
                'tradingsymbol': tradingsymbol,
                'exchange': exchange,
                'symbol': parsed['symbol'],
                'strike': parsed['strike'],
                'option_type': parsed['option_type'],
                'expiry': parsed['expiry'],
                'strategy': parsed['strategy'],
                'quantity': abs(quantity),
                'is_short': is_short,
                'average_price': average_price,
                'last_price': last_price,
                'premium': premium,
                'm2m': m2m,
                'realised_pnl': realised_pnl,
                'unrealised_pnl': unrealised_pnl,
                'buy_quantity': buy_quantity,
                'sell_quantity': sell_quantity,
                'pending_orders': pos.get('pending_orders', 0),
                'collateral': pos.get('collateral', 0),
                'v': pos.get('v', 0),  # Valuation
            }
            
            all_positions.append(position)
        
        # Group positions by underlying symbol and expiry to form spreads
        return group_positions_into_spreads(all_positions)
        
    except Exception as e:
        logger.error(f"Failed to fetch live positions: {e}")
        return []


def group_positions_into_spreads(positions: list[dict]) -> list[dict]:
    """
    Group individual option positions into spreads based on:
    - Same underlying symbol
    - Same expiry
    - Same strategy (PE for Bull Put, CE for Bear Call)
    """
    from collections import defaultdict
    
    # Group by symbol + expiry + strategy
    groups = defaultdict(list)
    
    for pos in positions:
        key = f"{pos['symbol']}_{pos['expiry']}_{pos['strategy']}"
        groups[key].append(pos)
    
    spreads = []
    
    for key, group_positions in groups.items():
        if len(group_positions) < 2:
            # Single leg position - treat as spread with missing leg
            continue
        
        # Separate short and long legs
        short_legs = [p for p in group_positions if p['is_short']]
        long_legs = [p for p in group_positions if not p['is_short']]
        
        if not short_legs or not long_legs:
            continue
        
        # Take the first short and long leg (should be one each for simple spreads)
        short_leg = short_legs[0]
        long_leg = long_legs[0]
        
        spread = {
            'spread_id': key,
            'symbol': short_leg['symbol'],
            'strategy': short_leg['strategy'],
            'expiry': short_leg['expiry'],
            'short_strike': short_leg['strike'],
            'long_strike': long_leg['strike'],
            'short_leg': short_leg,
            'long_leg': long_leg,
            # Calculate net premium (credit if short > long, debit if long > short)
            'net_credit': (short_leg['average_price'] - long_leg['average_price']),
            'current_debit': (short_leg['last_price'] - long_leg['last_price']),
            # Calculate combined P&L
            'm2m': short_leg['m2m'] + long_leg['m2m'],
            'realised_pnl': short_leg['realised_pnl'] + long_leg['realised_pnl'],
            'unrealised_pnl': short_leg['unrealised_pnl'] + long_leg['unrealised_pnl'],
            'lot_size': min(short_leg['quantity'], long_leg['quantity']),
        }
        
        # Calculate spread P&L
        entry_credit = spread['net_credit']
        current_debit = spread['current_debit']
        lot_size = spread['lot_size']
        
        # P&L = Entry Credit - Current Debit (for credit spreads)
        spread_pnl = (entry_credit - current_debit) * lot_size
        spread['pnl'] = spread_pnl
        
        # Percentage
        if entry_credit > 0:
            spread['pnl_pct'] = ((entry_credit - current_debit) / entry_credit) * 100
        else:
            spread['pnl_pct'] = 0
        
        spreads.append(spread)
    
    return spreads


def get_positions(kite: KiteClient) -> dict:
    """Fetch current positions from Kite."""
    try:
        return kite.positions()
    except Exception as e:
        logger.error(f"Failed to fetch positions: {e}")
        return {'net': [], 'day': []}


def get_quote(kite: KiteClient, symbol: str) -> dict:
    """Fetch quote for a specific symbol."""
    try:
        quotes = kite.quote([symbol])
        return quotes.get(symbol, {})
    except Exception as e:
        logger.error(f"Failed to fetch quote for {symbol}: {e}")
        return {}


def get_quotes(kite: KiteClient, symbols: list[str]) -> dict:
    """Fetch quotes for multiple symbols."""
    try:
        return kite.quote(symbols)
    except Exception as e:
        logger.error(f"Failed to fetch quotes: {e}")
        return {}


# ──────────────────────────────────────────────
# Trade Execution Helpers
# ──────────────────────────────────────────────

def calculate_spread_pnl(trade: dict, current_prices: dict) -> dict:
    """
    Calculate current P&L for a spread trade.
    
    Parameters:
    -----------
    trade : dict
        Trade details from database
    current_prices : dict
        Current prices for short and long legs
    
    Returns:
    --------
    dict
        P&L details including current premium, P&L amount and percentage
    """
    # Reconstruct trading symbols
    try:
        exp_date = datetime.strptime(trade['expiry'], "%Y-%m-%d").date()
    except:
        exp_date = date.today()
    
    yy = str(exp_date.year)[-2:]
    mon = exp_date.strftime("%b").upper()
    leg_type = "PE" if "PUT" in trade['strategy'] else "CE"
    
    short_sym = f"NFO:{trade['symbol']}{yy}{mon}{int(trade['short_strike'])}{leg_type}"
    long_sym = f"NFO:{trade['symbol']}{yy}{mon}{int(trade['long_strike'])}{leg_type}"
    
    short_price = current_prices.get(short_sym, {}).get('last_price', 0)
    long_price = current_prices.get(long_sym, {}).get('last_price', 0)
    
    # Current spread debit (to close)
    current_debit = short_price - long_price
    entry_credit = trade['net_credit']
    
    # P&L = Entry Credit - Current Debit
    # If we sold at 25 and buy back at 12, profit = 13
    pnl = (entry_credit - current_debit) * trade['lot_size']
    
    # Percentage change
    if entry_credit > 0:
        pnl_pct = ((entry_credit - current_debit) / entry_credit) * 100
    else:
        pnl_pct = 0
    
    return {
        'current_debit': current_debit,
        'entry_credit': entry_credit,
        'pnl': pnl,
        'pnl_pct': pnl_pct,
        'short_price': short_price,
        'long_price': long_price,
    }


def get_exit_status(trade: dict, current_prices: dict) -> dict:
    """
    Check exit rule status for a trade.
    
    Returns:
    --------
    dict
        Status of each exit rule (target, SL, time stop)
    """
    import config
    
    pnl_data = calculate_spread_pnl(trade, current_prices)
    current_debit = pnl_data['current_debit']
    entry_credit = pnl_data['entry_credit']
    
    # Target: 50% profit (debit drops to 50% of credit)
    target_debit = entry_credit * (1 - config.SPREAD_TARGET_PCT / 100)
    target_hit = current_debit <= target_debit
    
    # Stop Loss: premium doubles (debit >= 2x credit)
    sl_debit = entry_credit * (1 + config.SPREAD_SL_PCT / 100)
    sl_hit = current_debit >= sl_debit
    
    # Time stop: Thursday 2:30 PM
    now = datetime.now()
    is_thursday = now.weekday() == 3
    is_expiry_time = now.time().hour >= 14 and now.time().minute >= 30
    time_stop_hit = is_thursday and is_expiry_time
    
    return {
        'target_hit': target_hit,
        'sl_hit': sl_hit,
        'time_stop_hit': time_stop_hit,
        'target_debit': target_debit,
        'sl_debit': sl_debit,
    }

