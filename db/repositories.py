"""
Database Repository Layer

Provides a clean abstraction over database operations using the repository pattern.
Each repository handles a specific domain entity with standardized CRUD operations.

Usage:
    from db.repositories import TradeRepository, ScanRepository
    
    trade_repo = TradeRepository()
    open_trades = trade_repo.get_all_open()
"""

import json
import logging
import uuid
from datetime import datetime, date
from typing import Any, Optional

from db.connection import get_connection

logger = logging.getLogger(__name__)


class BaseRepository:
    """Base repository with common database operations."""
    
    table_name: str = ""
    primary_key: str = "id"
    
    def _execute(self, query: str, params: tuple = ()) -> None:
        """Execute a query without returning results."""
        with get_connection() as conn:
            conn.execute(query, params)
    
    def _fetch_one(self, query: str, params: tuple = ()) -> Optional[dict]:
        """Execute a query and return a single row."""
        with get_connection() as conn:
            cursor = conn.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def _fetch_all(self, query: str, params: tuple = ()) -> list[dict]:
        """Execute a query and return all rows."""
        with get_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def _insert(self, query: str, params: tuple = ()) -> None:
        """Execute an insert query."""
        self._execute(query, params)
    
    def _update(self, query: str, params: tuple = ()) -> int:
        """Execute an update query and return affected rows."""
        with get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.rowcount
    
    def _delete(self, query: str, params: tuple = ()) -> int:
        """Execute a delete query and return affected rows."""
        with get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.rowcount


class TradeRepository(BaseRepository):
    """Repository for trade_log table operations."""
    
    table_name = "trade_log"
    primary_key = "trade_id"
    
    # -------------------------------------------------------------------------
    # Read Operations
    # -------------------------------------------------------------------------
    
    def get_by_id(self, trade_id: str) -> Optional[dict]:
        """Get a trade by its ID."""
        return self._fetch_one(
            "SELECT * FROM trade_log WHERE trade_id = ?",
            (trade_id,)
        )
    
    def get_all_open(self) -> list[dict]:
        """Get all open trades."""
        return self._fetch_all(
            "SELECT * FROM trade_log WHERE status = 'OPEN' ORDER BY entry_time DESC"
        )
    
    def get_all_closed(self, limit: int = 100) -> list[dict]:
        """Get all closed trades."""
        return self._fetch_all(
            """SELECT * FROM trade_log 
               WHERE status = 'CLOSED' 
               AND exit_time IS NOT NULL
               ORDER BY exit_time DESC 
               LIMIT ?""",
            (limit,)
        )
    
    def get_today_trades(self) -> list[dict]:
        """Get all trades entered today."""
        today = date.today().isoformat()
        return self._fetch_all(
            """SELECT * FROM trade_log 
               WHERE date(entry_time) = ? 
               ORDER BY entry_time DESC""",
            (today,)
        )
    
    def get_by_symbol(self, symbol: str, status: Optional[str] = None) -> list[dict]:
        """Get trades by symbol, optionally filtered by status."""
        if status:
            return self._fetch_all(
                "SELECT * FROM trade_log WHERE symbol = ? AND status = ? ORDER BY entry_time DESC",
                (symbol, status)
            )
        return self._fetch_all(
            "SELECT * FROM trade_log WHERE symbol = ? ORDER BY entry_time DESC",
            (symbol,)
        )
    
    def get_by_strategy(self, strategy: str) -> list[dict]:
        """Get trades by strategy type."""
        return self._fetch_all(
            "SELECT * FROM trade_log WHERE strategy = ? ORDER BY entry_time DESC",
            (strategy,)
        )
    
    def count_open_trades(self) -> int:
        """Count total open trades."""
        result = self._fetch_one("SELECT COUNT(*) as count FROM trade_log WHERE status = 'OPEN'")
        return result['count'] if result else 0
    
    def count_open_for_symbol(self, symbol: str) -> int:
        """Count open trades for a specific symbol."""
        result = self._fetch_one(
            "SELECT COUNT(*) as count FROM trade_log WHERE symbol = ? AND status = 'OPEN'",
            (symbol,)
        )
        return result['count'] if result else 0
    
    def get_pnl_summary(self) -> dict[str, Any]:
        """Get P&L summary statistics."""
        # Today's P&L
        today = date.today().isoformat()
        today_result = self._fetch_one(
            """SELECT SUM(pnl) as total_pnl, COUNT(*) as trade_count
               FROM trade_log 
               WHERE date(exit_time) = ? AND status = 'CLOSED'""",
            (today,)
        )
        
        # Month-to-date P&L
        mtd_result = self._fetch_one(
            """SELECT SUM(pnl) as total_pnl
               FROM trade_log 
               WHERE status = 'CLOSED'
               AND exit_time IS NOT NULL
               AND strftime('%Y-%m', exit_time) = strftime('%Y-%m', 'now')"""
        )
        
        # All-time stats
        all_time_result = self._fetch_one(
            """SELECT SUM(pnl) as total_pnl,
                      COUNT(CASE WHEN pnl > 0 THEN 1 END) as wins,
                      COUNT(CASE WHEN pnl < 0 THEN 1 END) as losses
               FROM trade_log 
               WHERE status = 'CLOSED' AND pnl IS NOT NULL"""
        )
        
        return {
            'today_pnl': today_result.get('total_pnl', 0) or 0,
            'today_trades': today_result.get('trade_count', 0) or 0,
            'mtd_pnl': mtd_result.get('total_pnl', 0) or 0,
            'all_time_pnl': all_time_result.get('total_pnl', 0) or 0,
            'total_wins': all_time_result.get('wins', 0) or 0,
            'total_losses': all_time_result.get('losses', 0) or 0,
        }
    
    # -------------------------------------------------------------------------
    # Write Operations
    # -------------------------------------------------------------------------
    
    def create(self, trade_data: dict) -> str:
        """Create a new trade record."""
        trade_id = str(uuid.uuid4())
        
        self._insert(
            """INSERT INTO trade_log (
                trade_id, symbol, strategy, status, mode,
                entry_time, short_strike, long_strike, expiry, lot_size,
                entry_short_pr, entry_long_pr, net_credit, sl_price, target_price,
                short_order_id, long_order_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trade_id,
                trade_data['symbol'],
                trade_data['strategy'],
                trade_data.get('status', 'OPEN'),
                trade_data.get('mode', 'PAPER'),
                datetime.now().isoformat(),
                trade_data['short_strike'],
                trade_data['long_strike'],
                trade_data['expiry'],
                trade_data['lot_size'],
                trade_data['entry_short_pr'],
                trade_data['entry_long_pr'],
                trade_data['net_credit'],
                trade_data.get('sl_price'),
                trade_data.get('target_price'),
                trade_data.get('short_order_id'),
                trade_data.get('long_order_id'),
            )
        )
        
        logger.info(f"Created trade {trade_id} for {trade_data['symbol']}")
        return trade_id
    
    def update_exit(self, trade_id: str, exit_data: dict) -> bool:
        """Update trade with exit information."""
        affected = self._update(
            """UPDATE trade_log SET
                status = 'CLOSED',
                exit_time = ?,
                exit_short_pr = ?,
                exit_long_pr = ?,
                pnl = ?,
                exit_reason = ?
            WHERE trade_id = ?""",
            (
                datetime.now().isoformat(),
                exit_data['exit_short_pr'],
                exit_data['exit_long_pr'],
                exit_data['pnl'],
                exit_data['exit_reason'],
                trade_id,
            )
        )
        
        if affected > 0:
            logger.info(f"Updated trade {trade_id} with exit: {exit_data['exit_reason']}")
            return True
        return False
    
    def update_status(self, trade_id: str, status: str) -> bool:
        """Update trade status."""
        affected = self._update(
            "UPDATE trade_log SET status = ? WHERE trade_id = ?",
            (status, trade_id)
        )
        return affected > 0
    
    def update_order_ids(self, trade_id: str, short_order_id: str, long_order_id: str) -> bool:
        """Update order IDs for a trade."""
        affected = self._update(
            "UPDATE trade_log SET short_order_id = ?, long_order_id = ? WHERE trade_id = ?",
            (short_order_id, long_order_id, trade_id)
        )
        return affected > 0
    
    def delete(self, trade_id: str) -> bool:
        """Delete a trade record."""
        affected = self._delete(
            "DELETE FROM trade_log WHERE trade_id = ?",
            (trade_id,)
        )
        return affected > 0


class ScanRepository(BaseRepository):
    """Repository for scan_results table operations."""
    
    table_name = "scan_results"
    primary_key = "scan_id"
    
    # -------------------------------------------------------------------------
    # Read Operations
    # -------------------------------------------------------------------------
    
    def get_by_id(self, scan_id: str) -> Optional[dict]:
        """Get a scan by its ID."""
        result = self._fetch_one(
            "SELECT * FROM scan_results WHERE scan_id = ?",
            (scan_id,)
        )
        
        if result and result.get('candidates'):
            result['candidates'] = json.loads(result['candidates'])
        
        return result
    
    def get_all(self, limit: int = 20) -> list[dict]:
        """Get all scans, most recent first."""
        scans = self._fetch_all(
            "SELECT * FROM scan_results ORDER BY scan_time DESC LIMIT ?",
            (limit,)
        )
        
        for scan in scans:
            if scan.get('candidates'):
                scan['candidates'] = json.loads(scan['candidates'])
        
        return scans
    
    def get_recent(self, hours: int = 24) -> list[dict]:
        """Get scans from the last N hours."""
        scans = self._fetch_all(
            """SELECT * FROM scan_results 
               WHERE datetime(scan_time) >= datetime('now', ?)
               ORDER BY scan_time DESC""",
            (f'-{hours} hours',)
        )
        
        for scan in scans:
            if scan.get('candidates'):
                scan['candidates'] = json.loads(scan['candidates'])
        
        return scans
    
    # -------------------------------------------------------------------------
    # Write Operations
    # -------------------------------------------------------------------------
    
    def create(self, candidates: list[dict], min_ivp: float, min_hv_rank: float, 
               total_scanned: int) -> str:
        """Save a new scan result."""
        scan_id = str(uuid.uuid4())
        scan_time = datetime.now().isoformat()
        candidates_json = json.dumps(candidates)
        
        self._insert(
            """INSERT INTO scan_results 
               (scan_id, scan_time, min_ivp, min_hv_rank, total_scanned, candidates_found, candidates)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (scan_id, scan_time, min_ivp, min_hv_rank, total_scanned, len(candidates), candidates_json)
        )
        
        logger.info(f"Saved scan {scan_id} with {len(candidates)} candidates")
        return scan_id
    
    def delete(self, scan_id: str) -> bool:
        """Delete a scan result."""
        affected = self._delete(
            "DELETE FROM scan_results WHERE scan_id = ?",
            (scan_id,)
        )
        return affected > 0
    
    def delete_old(self, days: int = 30) -> int:
        """Delete scans older than N days."""
        affected = self._delete(
            "DELETE FROM scan_results WHERE datetime(scan_time) < datetime('now', ?)",
            (f'-{days} days',)
        )
        logger.info(f"Deleted {affected} old scans")
        return affected


class IVHistoryRepository(BaseRepository):
    """Repository for iv_history table operations."""
    
    table_name = "iv_history"
    primary_key = "id"
    
    # -------------------------------------------------------------------------
    # Read Operations
    # -------------------------------------------------------------------------
    
    def get_by_symbol(self, symbol: str, limit: int = 365) -> list[dict]:
        """Get IV history for a symbol."""
        return self._fetch_all(
            """SELECT * FROM iv_history 
               WHERE stock_symbol = ? 
               ORDER BY timestamp DESC 
               LIMIT ?""",
            (symbol, limit)
        )
    
    def get_latest(self, symbol: str) -> Optional[dict]:
        """Get the latest IV record for a symbol."""
        return self._fetch_one(
            """SELECT * FROM iv_history 
               WHERE stock_symbol = ? 
               ORDER BY timestamp DESC 
               LIMIT 1""",
            (symbol,)
        )
    
    def get_symbols_with_data_today(self) -> set[str]:
        """Get symbols that already have data for today."""
        today_str = datetime.now().strftime("%Y-%m-%d")
        rows = self._fetch_all(
            "SELECT stock_symbol FROM iv_history WHERE timestamp = ?",
            (today_str,)
        )
        return {row['stock_symbol'] for row in rows}
    
    def get_iv_series(self, symbol: str, days: int = 30) -> list[float]:
        """Get IV values for the last N days."""
        rows = self._fetch_all(
            """SELECT atm_iv FROM iv_history 
               WHERE stock_symbol = ? 
               ORDER BY timestamp DESC 
               LIMIT ?""",
            (symbol, days)
        )
        return [row['atm_iv'] for row in rows if row.get('atm_iv')]
    
    # -------------------------------------------------------------------------
    # Write Operations
    # -------------------------------------------------------------------------
    
    def upsert(self, symbol: str, atm_iv: float, hv_20_day: Optional[float] = None) -> None:
        """Insert or update IV data for a symbol (today's date)."""
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        with get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO iv_history 
                   (stock_symbol, timestamp, atm_iv, hv_20_day)
                   VALUES (?, ?, ?, ?)""",
                (symbol, today_str, atm_iv, hv_20_day)
            )
        
        logger.debug(f"Updated IV for {symbol}: IV={atm_iv}, HV={hv_20_day}")


class ConfigRepository(BaseRepository):
    """Repository for config_settings table operations."""
    
    table_name = "config_settings"
    primary_key = "key"
    
    # -------------------------------------------------------------------------
    # Read Operations
    # -------------------------------------------------------------------------
    
    def get(self, key: str, default: Any = None) -> Optional[str]:
        """Get a config value by key."""
        result = self._fetch_one(
            "SELECT value FROM config_settings WHERE key = ?",
            (key,)
        )
        return result['value'] if result else default
    
    def get_int(self, key: str, default: int = 0) -> int:
        """Get a config value as integer."""
        value = self.get(key)
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get a config value as float."""
        value = self.get(key)
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a config value as boolean."""
        value = self.get(key)
        if value is None:
            return default
        return value.lower() in ('true', '1', 'yes', 'on')
    
    def get_all(self) -> dict[str, str]:
        """Get all config settings."""
        rows = self._fetch_all("SELECT key, value FROM config_settings")
        return {row['key']: row['value'] for row in rows}
    
    # -------------------------------------------------------------------------
    # Write Operations
    # -------------------------------------------------------------------------
    
    def set(self, key: str, value: Any, description: Optional[str] = None) -> None:
        """Set a config value."""
        now = datetime.now().isoformat()
        
        with get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO config_settings (key, value, updated_at, description)
                   VALUES (?, ?, ?, ?)""",
                (key, str(value), now, description)
            )
        
        logger.info(f"Set config '{key}' = {value}")
    
    def delete(self, key: str) -> bool:
        """Delete a config setting."""
        affected = self._delete(
            "DELETE FROM config_settings WHERE key = ?",
            (key,)
        )
        return affected > 0


class ScanHistoryRepository(BaseRepository):
    """Repository for scan_history table operations."""
    
    table_name = "scan_history"
    primary_key = "id"
    
    # -------------------------------------------------------------------------
    # Read Operations
    # -------------------------------------------------------------------------
    
    def get_by_scan_id(self, scan_id: str) -> list[dict]:
        """Get all records for a specific scan run."""
        return self._fetch_all(
            """SELECT * FROM scan_history 
               WHERE scan_id = ? 
               ORDER BY score DESC NULLS LAST""",
            (scan_id,)
        )
    
    def get_qualified_by_scan_id(self, scan_id: str) -> list[dict]:
        """Get only qualified records for a specific scan run."""
        return self._fetch_all(
            """SELECT * FROM scan_history 
               WHERE scan_id = ? AND qualified = 1 
               ORDER BY score DESC""",
            (scan_id,)
        )
    
    def get_latest_scan(self) -> Optional[dict]:
        """Get the most recent scan metadata."""
        return self._fetch_one(
            """SELECT scan_id, scan_time, COUNT(*) as total_stocks,
                      SUM(qualified) as qualified_count
               FROM scan_history 
               GROUP BY scan_id 
               ORDER BY scan_time DESC 
               LIMIT 1"""
        )
    
    def get_all_scans(self, limit: int = 50) -> list[dict]:
        """Get all scan runs with summary stats."""
        return self._fetch_all(
            """SELECT scan_id, scan_time, COUNT(*) as total_stocks,
                      SUM(qualified) as qualified_count,
                      MIN(min_score_threshold) as min_score_threshold
               FROM scan_history 
               GROUP BY scan_id 
               ORDER BY scan_time DESC 
               LIMIT ?""",
            (limit,)
        )
    
    def get_symbol_history(self, symbol: str, limit: int = 30) -> list[dict]:
        """Get scan history for a specific symbol."""
        return self._fetch_all(
            """SELECT * FROM scan_history 
               WHERE symbol = ? 
               ORDER BY scan_time DESC 
               LIMIT ?""",
            (symbol, limit)
        )
    
    def get_recent_qualified(self, days: int = 7, limit: int = 100) -> list[dict]:
        """Get all qualified stocks from recent scans."""
        return self._fetch_all(
            """SELECT * FROM scan_history 
               WHERE qualified = 1 
               AND date(scan_time) >= date('now', ?)
               ORDER BY scan_time DESC, score DESC 
               LIMIT ?""",
            (f'-{days} days', limit)
        )
    
    # -------------------------------------------------------------------------
    # Write Operations
    # -------------------------------------------------------------------------
    
    def insert_scan_result(
        self,
        scan_id: str,
        scan_time: str,
        symbol: str,
        score: Optional[float],
        method: Optional[str],
        trend: Optional[str],
        ema_50: Optional[float],
        spot_price: Optional[float],
        atm_iv: Optional[float],
        hv_20: Optional[float],
        qualified: bool,
        min_score_threshold: float,
    ) -> None:
        """Insert a single scan result."""
        self._insert(
            """INSERT OR REPLACE INTO scan_history 
               (scan_id, scan_time, symbol, score, method, trend, ema_50, 
                spot_price, atm_iv, hv_20, qualified, min_score_threshold)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                scan_id,
                scan_time,
                symbol,
                score,
                method,
                trend,
                ema_50,
                spot_price,
                atm_iv,
                hv_20,
                1 if qualified else 0,
                min_score_threshold,
            )
        )
    
    def bulk_insert_scan_results(self, results: list[dict]) -> None:
        """Bulk insert scan results for efficiency."""
        if not results:
            return
        
        with get_connection() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO scan_history 
                   (scan_id, scan_time, symbol, score, method, trend, ema_50, 
                    spot_price, atm_iv, hv_20, qualified, min_score_threshold)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        r['scan_id'],
                        r['scan_time'],
                        r['symbol'],
                        r.get('score'),
                        r.get('method'),
                        r.get('trend'),
                        r.get('ema_50'),
                        r.get('spot_price'),
                        r.get('atm_iv'),
                        r.get('hv_20'),
                        1 if r.get('qualified', False) else 0,
                        r['min_score_threshold'],
                    )
                    for r in results
                ]
            )
    
    def delete_scan(self, scan_id: str) -> int:
        """Delete all records for a scan run."""
        return self._delete(
            "DELETE FROM scan_history WHERE scan_id = ?",
            (scan_id,)
        )
    
    def cleanup_old_scans(self, days_to_keep: int = 90) -> int:
        """Delete scan records older than specified days."""
        cutoff = datetime.now().strftime("%Y-%m-%d")
        with get_connection() as conn:
            cursor = conn.execute(
                """DELETE FROM scan_history 
                   WHERE date(scan_time) < date(?, ?)""",
                (cutoff, f'-{days_to_keep} days')
            )
            return cursor.rowcount


# Convenience instances
trade_repo = TradeRepository()
scan_repo = ScanRepository()
iv_history_repo = IVHistoryRepository()
config_repo = ConfigRepository()
scan_history_repo = ScanHistoryRepository()
