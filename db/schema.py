"""
Database schema definitions and migration logic.

Tables
------
iv_history  — Daily IV/HV snapshots per stock symbol.
trade_log   — Full lifecycle of every bot trade.

Run this module directly to initialise the database:
    python -m db.schema
"""

from db.connection import get_connection

# ──────────────────────────────────────────────
# DDL statements
# ──────────────────────────────────────────────

_CREATE_IV_HISTORY = """
CREATE TABLE IF NOT EXISTS iv_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_symbol  TEXT    NOT NULL,
    timestamp     TEXT    NOT NULL,            -- ISO-8601 datetime string
    atm_iv        REAL    NOT NULL,            -- At-the-money implied volatility (%)
    hv_20_day     REAL,                        -- 20-day historical volatility (%)
    UNIQUE(stock_symbol, timestamp)            -- prevent duplicate entries
);
"""

_CREATE_TRADE_LOG = """
CREATE TABLE IF NOT EXISTS trade_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id    TEXT    NOT NULL UNIQUE,        -- UUID identifying the trade
    symbol      TEXT    NOT NULL,
    entry_time  TEXT    NOT NULL,               -- ISO-8601
    exit_time   TEXT,                           -- NULL while position is open
    pnl         REAL,                           -- realised P&L (NULL while open)
    status      TEXT    NOT NULL DEFAULT 'OPEN' -- OPEN | CLOSED | EXPIRED | ERROR
);
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_iv_symbol ON iv_history(stock_symbol);",
    "CREATE INDEX IF NOT EXISTS idx_iv_ts     ON iv_history(timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_trade_sym ON trade_log(symbol);",
    "CREATE INDEX IF NOT EXISTS idx_trade_st  ON trade_log(status);",
]


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

def initialise_database() -> None:
    """Create all tables and indexes if they do not already exist."""
    with get_connection() as conn:
        conn.execute(_CREATE_IV_HISTORY)
        conn.execute(_CREATE_TRADE_LOG)
        for idx_sql in _CREATE_INDEXES:
            conn.execute(idx_sql)
    print("[db] Database initialised successfully.")


# Allow running directly: python -m db.schema
if __name__ == "__main__":
    initialise_database()
