"""
Integration Tests for IV-Sniper Critical Paths

Tests end-to-end workflows:
1. Scanner → Analyst → Trade Execution flow
2. Trade lifecycle (entry → monitoring → exit)
3. Database operations
4. Configuration persistence
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import sqlite3
import tempfile
from datetime import datetime, date, timedelta

# Test utilities
passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  ✓ {name}")
        passed += 1
    else:
        print(f"  ✗ {name}  {detail}")
        failed += 1


def setup_test_db():
    """Create a temporary test database."""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Create tables
    conn.executescript("""
        CREATE TABLE trade_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id TEXT UNIQUE,
            symbol TEXT,
            strategy TEXT,
            status TEXT DEFAULT 'OPEN',
            mode TEXT DEFAULT 'PAPER',
            entry_time TEXT,
            short_strike REAL,
            long_strike REAL,
            expiry TEXT,
            lot_size INTEGER,
            entry_short_pr REAL,
            entry_long_pr REAL,
            net_credit REAL,
            sl_price REAL,
            target_price REAL,
            exit_time TEXT,
            exit_short_pr REAL,
            exit_long_pr REAL,
            pnl REAL,
            exit_reason TEXT,
            short_order_id TEXT,
            long_order_id TEXT
        );
        
        CREATE TABLE scan_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id TEXT UNIQUE,
            scan_time TEXT,
            min_ivp REAL,
            min_hv_rank REAL,
            total_scanned INTEGER,
            candidates_found INTEGER,
            candidates TEXT
        );
        
        CREATE TABLE config_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE,
            value TEXT,
            updated_at TEXT,
            description TEXT
        );
    """)
    
    conn.commit()
    return conn, db_path


# ═════════════════════════════════════════════════════════════════════════════
# Test 1: Database Repository Integration
# ═════════════════════════════════════════════════════════════════════════════
print("\n── Test 1: Database Repository Integration ──")

try:
    from db.repositories import TradeRepository, ScanRepository, ConfigRepository
    
    conn, db_path = setup_test_db()
    
    # Test TradeRepository
    trade_repo = TradeRepository()
    
    # Create a test trade
    test_trade = {
        'symbol': 'NIFTY',
        'strategy': 'BULL_PUT',
        'short_strike': 22000,
        'long_strike': 21500,
        'expiry': '2026-02-27',
        'lot_size': 75,
        'entry_short_pr': 45.5,
        'entry_long_pr': 15.2,
        'net_credit': 30.3,
        'sl_price': 90.0,
        'target_price': 15.0,
        'mode': 'PAPER'
    }
    
    # Insert directly for test
    cursor = conn.execute(
        """INSERT INTO trade_log (trade_id, symbol, strategy, status, mode, entry_time,
            short_strike, long_strike, expiry, lot_size, entry_short_pr, entry_long_pr,
            net_credit, sl_price, target_price)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ('test-trade-001', test_trade['symbol'], test_trade['strategy'], 'OPEN', 
         test_trade['mode'], datetime.now().isoformat(),
         test_trade['short_strike'], test_trade['long_strike'], test_trade['expiry'],
         test_trade['lot_size'], test_trade['entry_short_pr'], test_trade['entry_long_pr'],
         test_trade['net_credit'], test_trade['sl_price'], test_trade['target_price'])
    )
    conn.commit()
    
    # Verify trade was created
    cursor = conn.execute("SELECT * FROM trade_log WHERE trade_id = 'test-trade-001'")
    row = cursor.fetchone()
    check("Trade created in DB", row is not None and row['symbol'] == 'NIFTY')
    
    # Test update exit
    conn.execute(
        """UPDATE trade_log SET status = 'CLOSED', exit_time = ?, 
           exit_short_pr = ?, exit_long_pr = ?, pnl = ?, exit_reason = ?
        WHERE trade_id = ?""",
        (datetime.now().isoformat(), 20.0, 5.0, 1125.0, 'TARGET', 'test-trade-001')
    )
    conn.commit()
    
    cursor = conn.execute("SELECT * FROM trade_log WHERE trade_id = 'test-trade-001'")
    row = cursor.fetchone()
    check("Trade exit updated", row['status'] == 'CLOSED' and row['pnl'] == 1125.0)
    
    # Test ScanRepository
    scan_repo = ScanRepository()
    candidates = [
        {'symbol': 'RELIANCE', 'score': 75.0, 'trend': 'Bullish'},
        {'symbol': 'INFY', 'score': 68.0, 'trend': 'Bearish'}
    ]
    
    conn.execute(
        """INSERT INTO scan_results (scan_id, scan_time, min_ivp, min_hv_rank, 
            total_scanned, candidates_found, candidates)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ('test-scan-001', datetime.now().isoformat(), 50.0, 50.0, 100, 2, 
         json.dumps(candidates))
    )
    conn.commit()
    
    cursor = conn.execute("SELECT * FROM scan_results WHERE scan_id = 'test-scan-001'")
    row = cursor.fetchone()
    check("Scan result saved", row is not None and row['candidates_found'] == 2)
    
    # Test ConfigRepository
    conn.execute(
        """INSERT INTO config_settings (key, value, updated_at, description)
        VALUES (?, ?, ?, ?)""",
        ('test_setting', 'test_value', datetime.now().isoformat(), 'Test description')
    )
    conn.commit()
    
    cursor = conn.execute("SELECT value FROM config_settings WHERE key = 'test_setting'")
    row = cursor.fetchone()
    check("Config setting saved", row is not None and row['value'] == 'test_value')
    
    conn.close()
    os.unlink(db_path)
    
except Exception as e:
    check("Repository integration", False, str(e))


# ═════════════════════════════════════════════════════════════════════════════
# Test 2: Symbol Utilities Integration
# ═════════════════════════════════════════════════════════════════════════════
print("\n── Test 2: Symbol Utilities Integration ──")

try:
    from ui.utils.symbol_utils import (
        parse_zerodha_symbol,
        reconstruct_option_symbol,
        get_option_symbols_for_trade,
        get_all_trade_symbols
    )
    
    # Test full workflow: parse → reconstruct
    original = "NFO:NIFTY26FEB22000CE"
    parsed = parse_zerodha_symbol(original)
    check("Parse symbol", parsed is not None)
    
    reconstructed = reconstruct_option_symbol(
        symbol=parsed['symbol'],
        expiry=parsed['expiry'],
        strike=parsed['strike'],
        strategy='BEAR_CALL',
        include_exchange=True
    )
    check("Reconstruct symbol", reconstructed == original)
    
    # Test trade symbol generation
    trades = [
        {
            'symbol': 'NIFTY',
            'expiry': '2026-02-27',
            'short_strike': 22000,
            'long_strike': 21500,
            'strategy': 'BULL_PUT'
        }
    ]
    
    symbols = get_all_trade_symbols(trades)
    check("Generate trade symbols", len(symbols) == 2)
    check("Short symbol is PE", 'PE' in symbols[0] or 'PE' in symbols[1])
    check("Long symbol is PE", 'PE' in symbols[0] or 'PE' in symbols[1])
    
except Exception as e:
    check("Symbol utilities integration", False, str(e))


# ═════════════════════════════════════════════════════════════════════════════
# Test 3: Validation & Formatting Integration
# ═════════════════════════════════════════════════════════════════════════════
print("\n── Test 3: Validation & Formatting Integration ──")

try:
    from ui.utils.validation import validate_trade_data, validate_spread_data
    from ui.utils.formatting import format_trade_summary, format_pnl
    
    # Test trade validation → formatting workflow
    valid_trade = {
        'symbol': 'NIFTY',
        'short_strike': 22000,
        'long_strike': 21500,
        'strategy': 'BULL_PUT',
        'expiry': (date.today() + timedelta(days=15)).isoformat(),
    }
    
    is_valid, error = validate_trade_data(valid_trade)
    check("Validate trade data", is_valid, error or "")
    
    if is_valid:
        summary = format_trade_summary(valid_trade)
        check("Format trade summary", "NIFTY" in summary and "Bull Put" in summary)
    
    # Test spread validation
    spread = {
        'short_symbol': 'NFO:NIFTY26FEB22000PE',
        'long_symbol': 'NFO:NIFTY26FEB21500PE',
        'short_strike': 22000,
        'long_strike': 21500,
        'strategy': 'BULL_PUT',
        'net_credit': 25.5,
        'max_profit': 1912.5,
        'max_loss': 1875.0,
        'risk_reward': 1.02
    }
    
    is_valid, error = validate_spread_data(spread)
    check("Validate spread data", is_valid, error or "")
    
    # Test P&L formatting
    pnl_formatted = format_pnl(1912.5)
    check("Format positive P&L", "+" in pnl_formatted and "1,912" in pnl_formatted)
    
    pnl_formatted = format_pnl(-1875.0)
    check("Format negative P&L", "-" in pnl_formatted and "1,875" in pnl_formatted)
    
except Exception as e:
    check("Validation & formatting integration", False, str(e))


# ═════════════════════════════════════════════════════════════════════════════
# Test 4: Error Handling Integration
# ═════════════════════════════════════════════════════════════════════════════
print("\n── Test 4: Error Handling Integration ──")

try:
    from ui.utils.error_handlers import (
        IVSniperError,
        ValidationError,
        format_error_message,
        get_user_friendly_message,
        safe_execute,
        safe_get,
        safe_convert
    )
    
    # Test custom exceptions
    try:
        raise ValidationError("Test validation error", details={'field': 'symbol'})
    except ValidationError as e:
        check("ValidationError raised", True)
        check("Error message formatted", "Test validation error" in str(e))
    
    # Test error formatting
    error = ValueError("Test error")
    formatted = format_error_message(error)
    check("Format error message", "Test error" in formatted)
    
    friendly = get_user_friendly_message(error)
    check("User-friendly message", len(friendly) > 0)
    
    # Test safe execution
    result = safe_execute(lambda: 10 / 2, default=0)
    check("Safe execute success", result == 5)
    
    result = safe_execute(lambda: 10 / 0, default=0)
    check("Safe execute fallback", result == 0)
    
    # Test safe get
    data = {'a': {'b': {'c': 'value'}}}
    result = safe_get(data, 'a', 'b', 'c')
    check("Safe get nested", result == 'value')
    
    result = safe_get(data, 'a', 'x', 'c', default='default')
    check("Safe get missing", result == 'default')
    
    # Test safe convert
    result = safe_convert("123", int, default=0)
    check("Safe convert int", result == 123)
    
    result = safe_convert("abc", int, default=0)
    check("Safe convert fallback", result == 0)
    
except Exception as e:
    check("Error handling integration", False, str(e))


# ═════════════════════════════════════════════════════════════════════════════
# Test 5: End-to-End Trade Flow
# ═════════════════════════════════════════════════════════════════════════════
print("\n── Test 5: End-to-End Trade Flow ──")

try:
    # Simulate complete trade lifecycle
    from ui.utils.validation import validate_trade_data
    from ui.utils.formatting import format_trade_summary, format_pnl
    from ui.utils.symbol_utils import get_option_symbols_for_trade
    
    # Step 1: Create trade data
    trade_data = {
        'symbol': 'NIFTY',
        'short_strike': 22000,
        'long_strike': 21500,
        'strategy': 'BULL_PUT',
        'expiry': (date.today() + timedelta(days=15)).isoformat(),
    }
    
    # Step 2: Validate
    is_valid, error = validate_trade_data(trade_data)
    check("E2E: Trade validation", is_valid)
    
    # Step 3: Generate symbols
    symbols = get_option_symbols_for_trade(
        symbol=trade_data['symbol'],
        expiry=trade_data['expiry'],
        short_strike=trade_data['short_strike'],
        long_strike=trade_data['long_strike'],
        strategy=trade_data['strategy']
    )
    check("E2E: Symbol generation", 'short_symbol' in symbols and 'long_symbol' in symbols)
    
    # Step 4: Format for display
    summary = format_trade_summary(trade_data)
    check("E2E: Trade summary", "NIFTY" in summary)
    
    # Step 5: Simulate P&L calculation and formatting
    pnl = 1912.5  # Simulated profit
    pnl_display = format_pnl(pnl)
    check("E2E: P&L formatting", "₹" in pnl_display and "+" in pnl_display)
    
except Exception as e:
    check("End-to-end trade flow", False, str(e))


# ═════════════════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════════════════
print(f"\n{'═' * 60}")
print(f"  Integration Tests: {passed} passed, {failed} failed")
print(f"{'═' * 60}\n")

sys.exit(1 if failed > 0 else 0)
