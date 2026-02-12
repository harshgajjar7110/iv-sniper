"""
Order Manager — Handles order placement and logging.

Supports:
- Paper Trading: Simulates orders and logs to DB.
- Live Trading: Places real Limit orders on Zerodha.
- Trade Logging: Persists all trade details to SQLite.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Tuple

from core.kite_client import KiteClient
from db.connection import get_connection
import config

logger = logging.getLogger(__name__)


class OrderManager:
    """Manages order execution and logging."""

    def __init__(self, kite: KiteClient):
        self.kite = kite

    def place_spread_order(
        self,
        symbol: str,
        spread: dict[str, Any],
        is_paper: bool = config.PAPER_TRADE_MODE,
    ) -> bool:
        """
        Execute the spread trade (Paper or Live).
        
        Returns True if successful, False otherwise.
        """
        trade_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # Extract details
        short_sym = spread["short_symbol"]
        long_sym = spread["long_symbol"]
        short_strike = spread["short_strike"]
        long_strike = spread["long_strike"]
        strategy = spread["type"]  # BULL_PUT / BEAR_CALL
        lot_size = spread["lot_size"]
        
        # Premiums from Analyst (LTPs) or fresh quote?
        # Better to fetch fresh quote for execution to be precise
        # But for paper mode, Analyst's LTP is fine as "fill price"
        # Let's use Analyst's premia for now to avoid race conditions in simulation
        entry_short_pr = spread["short_premium"]
        entry_long_pr = spread["long_premium"]
        net_credit = spread["net_credit"]
        
        # SL / Target
        sl_price = spread["sl_premium"]
        target_price = spread["target_premium"]
        
        mode = "PAPER" if is_paper else "LIVE"
        status = "OPEN"
        short_order_id = f"PAPER_SHORT_{trade_id[:8]}"
        long_order_id = f"PAPER_LONG_{trade_id[:8]}"
        
        logger.info(f"Executing {mode} {strategy} on {symbol} (Trade ID: {trade_id})")
        
        if not is_paper:
            # ── Live Execution ──
            try:
                # 1. Place Long Leg first (Hedge) for margin benefit
                long_order_id = self._place_leg(
                    symbol=long_sym,
                    transaction_type="BUY",
                    quantity=lot_size,
                    price=entry_long_pr * 1.05, # 5% buffer for limit buy
                    tag=f"IV_BOT_LONG_{trade_id[:8]}"
                )
                
                # 2. Place Short Leg
                short_order_id = self._place_leg(
                    symbol=short_sym,
                    transaction_type="SELL",
                    quantity=lot_size,
                    price=entry_short_pr * 0.95, # 5% buffer for limit sell
                    tag=f"IV_BOT_SHORT_{trade_id[:8]}"
                )
                
                logger.info(f"Live orders placed. Short: {short_order_id}, Long: {long_order_id}")
                
            except Exception as e:
                logger.error(f"Live order placement failed: {e}")
                # TODO: If long placed but short failed, we have a naked buy. 
                # Should reverse long? For now, just log error.
                return False

        # ── Log to Database ──
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO trade_log (
                        trade_id, symbol, strategy, status, mode,
                        entry_time, short_strike, long_strike, expiry, lot_size,
                        entry_short_pr, entry_long_pr, net_credit, 
                        sl_price, target_price,
                        short_order_id, long_order_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        trade_id, symbol, strategy, status, mode,
                        timestamp, short_strike, long_strike, str(spread["expiry"]), lot_size,
                        entry_short_pr, entry_long_pr, net_credit,
                        sl_price, target_price,
                        short_order_id, long_order_id
                    )
                )
            logger.info("Trade logged to DB successfully.")
            return True
            
        except Exception as e:
            logger.error(f"Failed to log trade to DB: {e}")
            return False

    def _place_leg(self, symbol: str, transaction_type: str, quantity: int, price: float, tag: str) -> str:
        """Helper to place a single leg order on Kite."""
        # Convert explicit price to tick size if needed, mostly handled by Kite?
        # Kite expects price (float).
        
        order_id = self.kite.place_order(
            tradingsymbol=symbol,
            exchange="NFO",
            transaction_type=transaction_type,
            quantity=quantity,
            order_type="LIMIT",
            product="NRML", # Overnight
            price=round(price, 1), # Round to tick size? Assuming 0.05 tick, 1 decimal safe for >50?
            variety="regular",
            tag=tag
        )
        return order_id
        
    def prepare_basket_orders(self, spread: dict[str, Any]) -> list[dict]:
        """Format orders for margin check API."""
        # Basket margins requires specific list format
        # [ {exchange, tradingsymbol, transaction_type, variety, product, order_type, quantity, price} ]
        
        orders = []
        
        # Long leg
        orders.append({
            "exchange": "NFO",
            "tradingsymbol": spread["long_symbol"],
            "transaction_type": "BUY",
            "variety": "regular",
            "product": "NRML",
            "order_type": "LIMIT",
            "quantity": spread["lot_size"],
            "price": spread["long_premium"]
        })
        
        # Short leg
        orders.append({
            "exchange": "NFO",
            "tradingsymbol": spread["short_symbol"],
            "transaction_type": "SELL",
            "variety": "regular",
            "product": "NRML",
            "order_type": "LIMIT",
            "quantity": spread["lot_size"],
            "price": spread["short_premium"]
        })
        
        return orders
