"""Configuration Store - Database-backed configuration settings.

Provides functions to save and load configuration settings from the database.
This allows runtime configuration changes without modifying config.py.
"""

import logging
from datetime import datetime
from typing import Any

from db.connection import get_connection

logger = logging.getLogger(__name__)


def save_setting(key: str, value: str, description: str = "") -> bool:
    """
    Save a configuration setting to the database.
    
    Args:
        key: Setting key (e.g., 'capital_risk_limit_pct')
        value: Setting value as string
        description: Optional description of the setting
    
    Returns:
        True if successful, False otherwise
    """
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO config_settings (key, value, updated_at, description)
                VALUES (?, ?, ?, ?)
                """,
                (key, value, datetime.now().isoformat(), description)
            )
        logger.info(f"Setting '{key}' saved successfully with value: {value}")
        return True
    except Exception as e:
        logger.error(f"Failed to save setting '{key}': {e}")
        return False


def load_setting(key: str, default: Any = None) -> Any:
    """
    Load a configuration setting from the database.
    
    Args:
        key: Setting key to load
        default: Default value if setting not found
    
    Returns:
        Setting value as string, or default if not found
    """
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT value FROM config_settings WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()
            if row:
                return row['value']
            return default
    except Exception as e:
        logger.warning(f"Failed to load setting '{key}': {e}")
        return default


def load_all_settings() -> dict:
    """
    Load all configuration settings from the database.
    
    Returns:
        Dictionary of key-value pairs
    """
    settings = {}
    try:
        with get_connection() as conn:
            cursor = conn.execute("SELECT key, value FROM config_settings")
            for row in cursor.fetchall():
                settings[row['key']] = row['value']
    except Exception as e:
        logger.warning(f"Failed to load all settings: {e}")
    return settings


def delete_setting(key: str) -> bool:
    """
    Delete a configuration setting from the database.
    
    Args:
        key: Setting key to delete
    
    Returns:
        True if successful, False otherwise
    """
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM config_settings WHERE key = ?", (key,))
        logger.info(f"Setting '{key}' deleted successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to delete setting '{key}': {e}")
        return False


# Convenience functions for common config types
def save_int_setting(key: str, value: int, description: str = "") -> bool:
    """Save an integer setting."""
    return save_setting(key, str(value), description)


def save_float_setting(key: str, value: float, description: str = "") -> bool:
    """Save a float setting."""
    return save_setting(key, str(value), description)


def save_bool_setting(key: str, value: bool, description: str = "") -> bool:
    """Save a boolean setting."""
    return save_setting(key, str(value).lower(), description)


def load_int_setting(key: str, default: int = 0) -> int:
    """Load an integer setting."""
    value = load_setting(key)
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        logger.warning(f"Invalid integer value for '{key}': {value}")
        return default


def load_float_setting(key: str, default: float = 0.0) -> float:
    """Load a float setting."""
    value = load_setting(key)
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        logger.warning(f"Invalid float value for '{key}': {value}")
        return default


def load_bool_setting(key: str, default: bool = False) -> bool:
    """Load a boolean setting."""
    value = load_setting(key)
    if value is None:
        return default
    return value.lower() in ('true', '1', 'yes', 'on')
