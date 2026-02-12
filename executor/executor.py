"""
Executor Orchestrator.

Coordinates the final trade execution pipeline:
1. Checks global safety (Nifty crash).
2. Filters for duplicate trades.
3. Validates individual trade safety (Bid-Ask spread, Margin).
4. Places orders via OrderManager.
"""

import logging
import time
from typing import Any

from core.kite_client import KiteClient
from db.connection import get_connection
from executor.capital_guard import (
    check_nifty_crash,
    check_bid_ask_spread,
    check_margin_and_capital,
    check_circuit_limits,
)
from executor.order_manager import OrderManager
import config

logger = logging.getLogger(__name__)


def execute_trades(
    recommendations: list[dict[str, Any]],
    kite: KiteClient,
) -> int:
    """
    Process trade recommendations and execute valid ones.
    Returns number of trades executed.
    """
    if not recommendations:
        return 0
        
    logger.info("═══ Starting Execution Phase ═══")
    
    # ── 1. Global Safety Checks ──
    if not check_nifty_crash(kite):
        logger.critical("Global Safety Triggered (Nifty Crash). Aborting all trades.")
        return 0
        
    # Check max open trades
    current_open = _get_open_trade_count()
    if current_open >= config.MAX_OPEN_TRADES:
        logger.warning(
            "Max open trades reached (%d/%d). Skipping execution.",
            current_open, config.MAX_OPEN_TRADES
        )
        return 0
        
    order_manager = OrderManager(kite)
    executed_count = 0
    
    for rec in recommendations:
        symbol = rec["symbol"]
        spread = rec["spread"]
        
        # ── 2. Duplicate Check ──
        if _is_duplicate_trade(symbol):
            logger.info("Skipping %s: Open trade already exists.", symbol)
            continue
            
        # ── 3. Live Quote Validation ──
        # Fetch Bid/Ask for spread validation
        short_sym = "NFO:" + spread["short_symbol"] # Kite format
        long_sym = "NFO:" + spread["long_symbol"]
        
        try:
            quotes = kite.quote([short_sym, long_sym])
        except Exception as e:
            logger.error("Failed to fetch quotes for validation: %s", e)
            continue
            
        short_quote = quotes.get(short_sym)
        long_quote = quotes.get(long_sym)
        
        if not short_quote or not long_quote:
            logger.warning("Quote missing for %s legs. Skipping.", symbol)
            continue
            
        # Check Circuit Limits (Liquidity Trap)
        if not check_circuit_limits(short_sym, short_quote):
            continue
        if not check_circuit_limits(long_sym, long_quote):
            continue
            
        # Validate Bid-Ask Spread on Short Leg (critical)
        # We sell at Bid (market/limit) or somewhere in between. 
        # If spread is wide, we lose value.
        short_depth = short_quote["depth"]
        # Use top bid/ask
        best_bid = short_depth["buy"][0]["price"]
        best_ask = short_depth["sell"][0]["price"]
        ltp = short_quote["last_price"]
        
        if not check_bid_ask_spread(short_sym, best_bid, best_ask, ltp):
            continue
            
        # ── 4. Margin Check ──
        # Format orders for margin check
        basket_orders = [
            {
                "exchange": "NFO",
                "tradingsymbol": spread["long_symbol"],
                "transaction_type": "BUY",
                "variety": "regular",
                "product": "NRML",
                "order_type": "LIMIT",
                "quantity": spread["lot_size"],
                "price": best_ask # Approx buy price
            },
            {
                "exchange": "NFO",
                "tradingsymbol": spread["short_symbol"],
                "transaction_type": "SELL",
                "variety": "regular",
                "product": "NRML",
                "order_type": "LIMIT",
                "quantity": spread["lot_size"],
                "price": best_bid # Approx sell price
            }
        ]
        
        if not check_margin_and_capital(kite, basket_orders):
            logger.info("Skipping %s due to margin/capital limits.", symbol)
            continue
            
        # ── 5. Execute ──
        # Update spread details with latest valid quotes if needed?
        # For paper trade, we just use the analyst values or these?
        # Analyst values are snapshot. Let's stick to them for consistency 
        # unless significant deviation. For now, use analyst values passed in `rec`.
        
        success = order_manager.place_spread_order(symbol, spread)
        if success:
            executed_count += 1
            logger.info("Successfully executed trade for %s", symbol)
            
            # Check max trades again
            if _get_open_trade_count() >= config.MAX_OPEN_TRADES:
                logger.info("Max trades limit reached. Stopping execution.")
                break
        
    return executed_count


def _is_duplicate_trade(symbol: str) -> bool:
    """Check if we already have an OPEN trade for this symbol."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT count(*) FROM trade_log WHERE symbol = ? AND status = 'OPEN'",
            (symbol,)
        )
        count = cursor.fetchone()[0]
    return count > 0

def _get_open_trade_count() -> int:
    """Get total number of open trades."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT count(*) FROM trade_log WHERE status = 'OPEN'"
        )
        count = cursor.fetchone()[0]
    return count
