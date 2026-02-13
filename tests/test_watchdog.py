"""
Test Watchdog — Mocked test for exit logic.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import MagicMock
from datetime import datetime
import sqlite3
import time

from db.schema import initialise_database
from db.connection import DB_PATH
from position_watchdog.monitor import run_watchdog
import config

class TestWatchdog(unittest.TestCase):
    def setUp(self):
        # Setup clean DB
        if os.path.exists(str(DB_PATH)):
            os.remove(str(DB_PATH))
        initialise_database()
        
        # Connect to insert dummy trade
        self.conn = sqlite3.connect(str(DB_PATH))
        
    def tearDown(self):
        self.conn.close()
        
    def _insert_trade(self, credit=20.0, sl_pct=100.0, target_pct=50.0):
        # Insert a dummy OPEN trade
        # Strategies: BULL_PUT -> Short PE, Long PE
        trade_id = "test_trade_1"
        self.conn.execute(
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
                trade_id, "TEST", "BULL_PUT", "OPEN", "PAPER",
                datetime.now().isoformat(), 1000, 950, "2025-12-25", 50,
                30.0, 10.0, credit, 
                0, 0, # sl/target price fields (ignored by new logic)
                "ord1", "ord2"
            )
        )
        self.conn.commit()
        return trade_id

    def test_profit_target_exit(self):
        # 1. Setup Trade with Credit 20. Target 50% -> Exit if Debit <= 10.
        self._insert_trade(credit=20.0)
        
        # 2. Mock Kite
        mock_kite = MagicMock()
        # Mock quote response: Short=14, Long=5 -> Debit = 9.
        # 9 < 10, so TARGET hit.
        short_sym = "TEST25DEC1000PE"
        long_sym = "TEST25DEC950PE"
        
        mock_kite.quote.return_value = {
            f"NFO:{short_sym}": {"last_price": 14.0},
            f"NFO:{long_sym}": {"last_price": 5.0}
        }
        
        # 3. Run Watchdog
        run_watchdog(mock_kite)
        
        # 4. Verify DB
        cursor = self.conn.execute("SELECT status, exit_reason, pnl FROM trade_log WHERE trade_id='test_trade_1'")
        row = cursor.fetchone()
        
        self.assertEqual(row[0], "CLOSED")
        self.assertEqual(row[1], "TARGET")
        # P&L = (Credit 20 - Debit 9) * Lot 50 = 11 * 50 = 550
        self.assertAlmostEqual(row[2], 550.0)
        print("✓ Profit Target test passed (P&L: 550.0)")

    def test_stop_loss_exit(self):
        # 1. Setup Trade with Credit 20. SL 100% -> Exit if Debit >= 40.
        config.SPREAD_SL_PCT = 100
        self._insert_trade(credit=20.0)
        
        # 2. Mock Kite
        mock_kite = MagicMock()
        # Mock quote: Short=50, Long=5 -> Debit = 45.
        # 45 >= 40, so SL hit.
        short_sym = "TEST25DEC1000PE"
        long_sym = "TEST25DEC950PE"
        
        mock_kite.quote.return_value = {
            f"NFO:{short_sym}": {"last_price": 50.0},
            f"NFO:{long_sym}": {"last_price": 5.0}
        }
        
        # 3. Run Watchdog
        run_watchdog(mock_kite)
        
        # 4. Verify
        cursor = self.conn.execute("SELECT status, exit_reason, pnl FROM trade_log WHERE trade_id='test_trade_1'")
        row = cursor.fetchone()
        
        self.assertEqual(row[0], "CLOSED")
        self.assertEqual(row[1], "SL")
        # P&L = (20 - 45) * 50 = -25 * 50 = -1250
        self.assertAlmostEqual(row[2], -1250.0)
        print("✓ Stop Loss test passed (P&L: -1250.0)")

    def test_no_exit(self):
        # 1. Setup Trade Credit 20. Debit 15. (Target 10, SL 40). No Exit.
        self._insert_trade(credit=20.0)
        
        mock_kite = MagicMock()
        short_sym = "TEST25DEC1000PE"
        long_sym = "TEST25DEC950PE"
        mock_kite.quote.return_value = {
            f"NFO:{short_sym}": {"last_price": 20.0},
            f"NFO:{long_sym}": {"last_price": 5.0}
        }
        
        run_watchdog(mock_kite)
        
        cursor = self.conn.execute("SELECT status FROM trade_log WHERE trade_id='test_trade_1'")
        row = cursor.fetchone()
        self.assertEqual(row[0], "OPEN")
        print("✓ No Exit test passed")

if __name__ == "__main__":
    unittest.main()
