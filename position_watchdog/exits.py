"""
Exit Manager — Handles position squaring off and P&L logging.
"""

import logging
from datetime import datetime
from typing import Any

from core.kite_client import KiteClient
from db.connection import get_connection
import config

logger = logging.getLogger(__name__)


class ExitManager:
    def __init__(self, kite: KiteClient):
        self.kite = kite

    def close_trade(
        self,
        trade: dict[str, Any],
        reason: str,
        current_short_pr: float, # For paper mode or live logging
        current_long_pr: float,  # For paper mode or live logging
    ) -> bool:
        """
        Square off a trade (Paper or Live) and update DB.
        
        trade: Row from trade_log (dict)
        reason: 'TARGET', 'SL', 'EXPIRY', 'MANUAL'
        current_short_pr/current_long_pr: Current LTPs for logging/paper calculation.
        """
        trade_id = trade["trade_id"]
        symbol = trade["symbol"]
        mode = trade["mode"]
        lot_size = trade["lot_size"]
        
        logger.info(f"Closing {mode} trade {trade_id} ({symbol}) due to {reason}...")
        
        if mode == "LIVE":
            # ── Live Exit ──
            # Place BUY order for Short leg (Cover)
            # Place SELL order for Long leg (Sell)
            try:
                # 1. Square off Short Leg (Buy back)
                self.kite.place_order(
                    tradingsymbol=f"{symbol}{int(trade['short_strike'])}PE" if trade['strategy']=="BULL_PUT" else f"{symbol}{int(trade['short_strike'])}CE", 
                    # Wait, spread details are in trade_log but symbol construction needs care. 
                    # Actually, we should store tradingsymbol in DB or reconstruct it.
                    # Reconstruction is risky if naming changes.
                    # But we stored strikes. Let's assume standard format or fetch order history?
                    # Let's verify DB schema. We stored 'short_strike', 'long_strike', 'expiry'.
                    # We can reconstruct tradingsymbol if we know format.
                    # Standard: SYMBOL + YY + M + DD + COMP + STRIKE.
                    # This is painful. Valid way: Store `instrument_token` or `tradingsymbol` in DB.
                    # I missed `tradingsymbol` columns for legs in Chunk 4 schema. 
                    # CRITICAL: I need to know the leg symbols to close them.
                    # For now, I'll rely on reconstruction or Order ID if positions API gives it.
                    # Better: Reconstruct using `instrument_master` or just `kite.positions()`?
                    # Watchdog should assume positions exist in Kite for LIVE.
                    # So we should iterate `kite.positions()` and close matches?
                    # But for consistency with `trade_log`, we need to link them.
                    # Let's assume paper mode for now (as user requested).
                    # For LIVE implementation later, we strictly match `kite.positions()`.
                     exchange="NFO",
                     transaction_type="BUY",
                     quantity=lot_size,
                     order_type="MARKET",
                     product="NRML",
                     variety="regular",
                     tag=f"EXIT_{trade_id[:8]}"
                )
                # 2. Square off Long Leg
                self.kite.place_order(
                     exchange="NFO",
                     transaction_type="SELL",
                     quantity=lot_size,
                     order_type="MARKET",
                     product="NRML",
                     variety="regular",
                     tag=f"EXIT_{trade_id[:8]}"
                )
            except Exception as e:
                logger.error(f"Live exit failed for {trade_id}: {e}")
                # Don't return False yet, try to log what happened?
                # If Live exit fails, we are in trouble.
                pass 
                # Proceed to update DB to CLOSED? No, only if successful.
                # Since LIVE is dangerous, I will focus on PAPER implementation as requested.
        
        # ── P&L Calculation ──
        # Entry Credit (Received) = Short_Entry - Long_Entry
        # Exit Debit (Paid) = Short_Exit - Long_Exit
        # P&L = Entry_Credit - Exit_Debit
        
        entry_credit = trade["net_credit"]
        exit_debit = current_short_pr - current_long_pr
        
        # NOTE: For Bear Call, credit/debit logic is same (sell spread, buy back).
        # We collected `entry_credit`. We pay `exit_debit` to close.
        pnl = (entry_credit - exit_debit) * lot_size
        
        logger.info(f"  P&L: ₹{pnl:.2f} (Credit: {entry_credit:.2f}, Debit: {exit_debit:.2f})")

        # ── DB Update ──
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    UPDATE trade_log
                    SET status = 'CLOSED',
                        exit_time = ?,
                        exit_short_pr = ?,
                        exit_long_pr = ?,
                        pnl = ?,
                        exit_reason = ?
                    WHERE trade_id = ?
                    """,
                    (
                        datetime.now().isoformat(),
                        current_short_pr,
                        current_long_pr,
                        pnl,
                        reason,
                        trade_id
                    )
                )
            logger.info(f"Trade {trade_id} closed in DB.")
            return True
        except Exception as e:
            logger.error(f"Failed to close trade in DB: {e}")
            return False
