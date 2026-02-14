"""
Database schema definitions and migration logic.

Tables
------
iv_history  — Daily IV/HV snapshots per stock symbol.
trade_log   — Full lifecycle of every bot trade.
scan_results — Saved scanner results with scan IDs.

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
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id      TEXT    NOT NULL UNIQUE,        -- UUID
    symbol        TEXT    NOT NULL,
    strategy      TEXT    NOT NULL,               -- BULL_PUT | BEAR_CALL
    status        TEXT    NOT NULL DEFAULT 'OPEN',-- OPEN | CLOSED | ERROR
    mode          TEXT    NOT NULL DEFAULT 'PAPER', -- PAPER | LIVE
    
    -- Entry Details
    entry_time    TEXT    NOT NULL,               -- ISO-8601
    short_strike  REAL    NOT NULL,
    long_strike   REAL    NOT NULL,
    expiry        TEXT    NOT NULL,               -- YYYY-MM-DD
    lot_size      INTEGER NOT NULL,
    
    -- Pricing & P&L
    entry_short_pr REAL   NOT NULL,               -- Premium received
    entry_long_pr  REAL   NOT NULL,               -- Premium paid
    net_credit     REAL   NOT NULL,
    sl_price       REAL,                          -- Stop Loss level (short leg premium)
    target_price   REAL,                          -- Target level (short leg premium)
    
    -- Exit Details
    exit_time      TEXT,
    exit_short_pr  REAL,
    exit_long_pr   REAL,
    pnl            REAL,                          -- Realised P&L
    exit_reason    TEXT,                          -- TARGET | SL | EXPIRY | MANUAL
    
    -- Order IDs (for live tracking)
    short_order_id TEXT,
    long_order_id  TEXT
);
"""

_CREATE_SCAN_RESULTS = """
CREATE TABLE IF NOT EXISTS scan_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id         TEXT    NOT NULL UNIQUE,       -- UUID for the scan
    scan_time       TEXT    NOT NULL,              -- ISO-8601 datetime when scan was run
    min_ivp         REAL    NOT NULL,              -- IVP threshold used
    min_hv_rank     REAL    NOT NULL,              -- HV Rank threshold used
    total_scanned   INTEGER NOT NULL,              -- Total stocks scanned
    candidates_found INTEGER NOT NULL,            -- Number of qualifying candidates
    -- Candidate details (JSON stored as TEXT)
    candidates      TEXT    NOT NULL               -- JSON array of candidate objects
);
"""

_CREATE_CONFIG_SETTINGS = """
CREATE TABLE IF NOT EXISTS config_settings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    key             TEXT    NOT NULL UNIQUE,       -- Setting key (e.g., 'capital_risk_limit_pct')
    value           TEXT    NOT NULL,              -- Setting value as text
    updated_at      TEXT    NOT NULL,              -- ISO-8601 datetime when updated
    description     TEXT                        -- Optional description
);
"""

_CREATE_SCAN_HISTORY = """
CREATE TABLE IF NOT EXISTS scan_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id         TEXT    NOT NULL,              -- UUID for the scan run (groups all stocks in same scan)
    scan_time       TEXT    NOT NULL,              -- ISO-8601 datetime when scan was run
    symbol          TEXT    NOT NULL,              -- Stock symbol (e.g., 'RELIANCE')
    score           REAL,                         -- IVP or HV Rank score (0-100)
    method          TEXT,                         -- 'IVP' or 'HV_RANK'
    trend           TEXT,                         -- 'Bullish' | 'Bearish' | 'Unknown'
    ema_50          REAL,                         -- 50-day EMA value
    spot_price      REAL,                         -- Current market price
    atm_iv          REAL,                         -- At-the-money implied volatility (%)
    hv_20           REAL,                         -- 20-day historical volatility (%)
    qualified       INTEGER NOT NULL DEFAULT 0,   -- 1 if passed threshold, 0 otherwise
    min_score_threshold REAL,                     -- Minimum score threshold used for this scan
    UNIQUE(scan_id, symbol)                       -- Prevent duplicate entries per scan
);
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_iv_symbol ON iv_history(stock_symbol);",
    "CREATE INDEX IF NOT EXISTS idx_iv_ts     ON iv_history(timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_trade_sym ON trade_log(symbol);",
    "CREATE INDEX IF NOT EXISTS idx_trade_st  ON trade_log(status);",
    "CREATE INDEX IF NOT EXISTS idx_scan_hist_scan_id ON scan_history(scan_id);",
    "CREATE INDEX IF NOT EXISTS idx_scan_hist_symbol ON scan_history(symbol);",
    "CREATE INDEX IF NOT EXISTS idx_scan_hist_time ON scan_history(scan_time);",
    "CREATE INDEX IF NOT EXISTS idx_scan_hist_qualified ON scan_history(qualified);",
]


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

def initialise_database() -> None:
    """Create all tables and indexes if they do not already exist."""
    with get_connection() as conn:
        conn.execute(_CREATE_IV_HISTORY)
        conn.execute(_CREATE_TRADE_LOG)
        conn.execute(_CREATE_SCAN_RESULTS)
        conn.execute(_CREATE_CONFIG_SETTINGS)
        conn.execute(_CREATE_SCAN_HISTORY)
        for idx_sql in _CREATE_INDEXES:
            conn.execute(idx_sql)
    print("[db] Database initialised successfully.")


# Allow running directly: python -m db.schema
if __name__ == "__main__":
    initialise_database()
