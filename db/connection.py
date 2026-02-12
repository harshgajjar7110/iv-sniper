"""
SQLite connection manager.

Provides a context-manager based connection so callers never leave
connections open accidentally.

Usage:
    from db.connection import get_connection

    with get_connection() as conn:
        conn.execute("SELECT ...")
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from config import DB_PATH


def _ensure_db_directory() -> None:
    """Create the data/ directory if it does not exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_connection():
    """
    Yield a sqlite3 Connection with WAL mode and foreign keys enabled.

    The connection auto-commits on clean exit and rolls back on exception.
    """
    _ensure_db_directory()
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row          # dict-like row access
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
