"""
Watchdog Monitor — background loop to check exit conditions.
"""

import logging
from datetime import datetime
from typing import Any

from core.kite_client import KiteClient
from db.connection import get_connection
from watchdog.exits import ExitManager
from ui.utils.symbol_utils import get_trade_symbols_dict
import config

logger = logging.getLogger(__name__)


def run_watchdog(kite: KiteClient):
    """
    Check all open trades for exit signals (Target, SL, Expiry).
    """
    exit_manager = ExitManager(kite)
    
    # 1. Get Open Trades
    open_trades = _get_open_trades()
    if not open_trades:
        logger.info("No open trades to monitor.")
        return

    logger.info(f"Monitoring {len(open_trades)} open trades...")

    # 2. Use utility function to get symbols for all trades
    try:
        trade_symbols = get_trade_symbols_dict(open_trades)
        all_instruments = []
        for sym_dict in trade_symbols.values():
            all_instruments.extend([sym_dict['short'], sym_dict['long']])
    except Exception as e:
        logger.error(f"Failed to get trade symbols: {e}")
        return

    if not all_instruments:
        return

    # 3. Fetch Quotes
    try:
        quotes = kite.quote(all_instruments)
    except Exception as e:
        logger.error(f"Watchdog failed to fetch quotes: {e}")
        return

    # 4. Check Conditions
    now = datetime.now()
    is_thursday = (now.weekday() == 3)
    # Expiry Check Time (e.g., 14:30)
    exp_time_cfg = datetime.strptime(config.EXPIRY_SQUARE_OFF_TIME, "%H:%M").time()
    is_expiry_panic = is_thursday and (now.time() >= exp_time_cfg)

    for t in open_trades:
        tid = t["trade_id"]
        syms = trade_symbols.get(tid)
        if not syms: continue
        
        s_key = f"NFO:{syms['short']}"
        l_key = f"NFO:{syms['long']}"
        
        if s_key not in quotes or l_key not in quotes:
            logger.warning(f"Missing quote for {t['symbol']} legs. Skipping.")
            continue
            
        s_ltp = quotes[s_key]["last_price"]
        l_ltp = quotes[l_key]["last_price"]
        
        # Calc Spread Value (Debit to Buy Back)
        # We Sold Short, Bought Long.
        # To Close: Buy Short, Sell Long.
        # Cost = s_ltp - l_ltp. (Since we want to pay little)
        
        current_spread_debit = s_ltp - l_ltp
        entry_credit = t["net_credit"]
        
        # P&L = Entry Credit - Current Debit
        # If Debit is small, we profit.
        
        # ── Exit Condition 1: Expiry Safety ──
        # Check if TODAY is the expiry date of this specific trade?
        # Or just "Every Thursday"? PRD says "If Day == Thursday... square off ALL positions".
        # Safe strategy: Check if trade expiry == today. 
        # But PRD implies "Avoid Physical Settlement", so strictly close on Expiry Day.
        
        trade_exp = datetime.strptime(t["expiry"], "%Y-%m-%d").date()
        is_trade_expiry_day = (trade_exp == now.date())
        
        if is_trade_expiry_day and now.time() >= exp_time_cfg:
             exit_manager.close_trade(t, "EXPIRY", s_ltp, l_ltp)
             continue
             
        # ── Exit Condition 2: Profit Target (50%) ──
        # If Current Debit <= 50% of Entry Credit
        target_debit = entry_credit * (1 - config.SPREAD_TARGET_PCT / 100.0) 
        # e.g., Credit 20. Target 50% -> Exit when Debit <= 10.
        
        if current_spread_debit <= target_debit:
            logger.info(f"Target Hit for {t['symbol']}: Spread {current_spread_debit:.2f} <= {target_debit:.2f}")
            exit_manager.close_trade(t, "TARGET", s_ltp, l_ltp)
            continue
            
        # ── Exit Condition 3: Stop Loss (200% / defined risk) ──
        # SL usually means "Premium doubles" -> Debit >= 2 * Credit.
        # Or based on Max Loss?
        # Config: SPREAD_SL_PCT = 100 (100% loss of credit? No, usually 100% gain in premium).
        # Let's assume SL_PCT relative to Credit.
        # If SL=100%, we exit when Debit = Credit * (1 + 100/100) = 2 * Credit.
        
        sl_debit = entry_credit * (1 + config.SPREAD_SL_PCT / 100.0)
        
        if current_spread_debit >= sl_debit:
             logger.info(f"Stop Loss Hit for {t['symbol']}: Spread {current_spread_debit:.2f} >= {sl_debit:.2f}")
             exit_manager.close_trade(t, "SL", s_ltp, l_ltp)
             continue
             
        # Log status
        pnl = (entry_credit - current_spread_debit) * t["lot_size"]
        logger.info(f"Monitoring {t['symbol']}: P&L ₹{pnl:.2f} | Spread {current_spread_debit:.2f} (Target {target_debit:.2f})")


def _get_open_trades() -> list[dict]:
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM trade_log WHERE status = 'OPEN'")
        return [dict(row) for row in cursor.fetchall()]
