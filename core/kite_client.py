"""
Zerodha Kite Connect wrapper.

Encapsulates API initialisation, session management, and common calls
needed by the bot. All other modules should use this instead of
importing kiteconnect directly.

Usage:
    from core.kite_client import KiteClient

    kite = KiteClient()
    kite.set_access_token("your_token")
    candles = kite.historical_data("NSE:RELIANCE", "day", 365)
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any

from kiteconnect import KiteConnect

import config

logger = logging.getLogger(__name__)


class KiteClient:
    """Thin wrapper around KiteConnect with retry logic."""

    def __init__(self) -> None:
        if not config.KITE_API_KEY:
            raise ValueError(
                "KITE_API_KEY is not set. "
                "Export it as an environment variable or update config.py."
            )
        self._kite = KiteConnect(api_key=config.KITE_API_KEY)

        # If an access token is already available, set it immediately
        if config.KITE_ACCESS_TOKEN:
            self._kite.set_access_token(config.KITE_ACCESS_TOKEN)

    # ── Session helpers ────────────────────────

    def get_login_url(self) -> str:
        """Return the Kite login URL for manual browser-based auth."""
        return self._kite.login_url()

    def generate_session(self, request_token: str) -> dict:
        """Exchange a request_token for an access_token and set it."""
        data = self._kite.generate_session(
            request_token, api_secret=config.KITE_API_SECRET
        )
        self._kite.set_access_token(data["access_token"])
        logger.info("Session established. Access token set.")
        return data

    def set_access_token(self, token: str) -> None:
        """Manually set the access token (e.g. from a stored file)."""
        self._kite.set_access_token(token)

    # ── Market data ────────────────────────────

    def historical_data(
        self,
        instrument_token: int,
        interval: str = "day",
        days: int = 365,
    ) -> list[dict[str, Any]]:
        """
        Fetch historical candles for the given instrument.

        Parameters
        ----------
        instrument_token : int
            Kite instrument token (not tradingsymbol).
        interval : str
            Candle interval — "minute", "3minute", "5minute",
            "15minute", "30minute", "60minute", "day".
        days : int
            Number of calendar days of history to fetch.

        Returns
        -------
        list[dict]
            Each dict has: date, open, high, low, close, volume.
        """
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days)
        return self._api_call_with_retry(
            self._kite.historical_data,
            instrument_token,
            from_date,
            to_date,
            interval,
        )

    def instruments(self, exchange: str = "NFO") -> list[dict]:
        """Fetch the full instrument master for an exchange."""
        return self._api_call_with_retry(self._kite.instruments, exchange)

    def ltp(self, symbols: list[str]) -> dict:
        """
        Get Last Traded Price for a list of instruments.

        Parameters
        ----------
        symbols : list[str]
            e.g. ["NSE:RELIANCE", "NFO:NIFTY23FEB18000CE"]

        Returns
        -------
        dict  — keyed by symbol, value contains 'last_price'.
        """
        return self._api_call_with_retry(self._kite.ltp, symbols)

    def quote(self, symbols: list[str]) -> dict:
        """Fetch full quote (bid/ask/oi/volume etc.) for symbols."""
        return self._api_call_with_retry(self._kite.quote, symbols)

    def margins(self) -> dict:
        """Fetch account margins (equity + commodity)."""
        return self._api_call_with_retry(self._kite.margins)

    def positions(self) -> dict:
        """Fetch current day and net positions."""
        return self._api_call_with_retry(self._kite.positions)

    # ── Order management ───────────────────────

    def place_order(self, **kwargs) -> str:
        """Place an order and return the order_id."""
        return self._api_call_with_retry(
            self._kite.place_order,
            variety=kwargs.pop("variety", self._kite.VARIETY_REGULAR),
            **kwargs,
        )

    def cancel_order(self, order_id: str, variety: str | None = None) -> str:
        """Cancel an open order."""
        variety = variety or self._kite.VARIETY_REGULAR
        return self._api_call_with_retry(
            self._kite.cancel_order, variety, order_id
        )

    # ── Internal helpers ───────────────────────

    def _api_call_with_retry(self, func, *args, **kwargs) -> Any:
        """
        Execute an API call with exponential backoff on rate-limit errors.

        Retries up to config.MAX_API_RETRIES times.
        """
        for attempt in range(1, config.MAX_API_RETRIES + 1):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                # Kite rate-limit errors surface as NetworkException or
                # InputException with specific messages.
                if "Too many requests" in str(exc) or "Rate limit" in str(exc):
                    wait = config.API_BACKOFF_BASE_SECONDS ** attempt
                    logger.warning(
                        "Rate limited (attempt %d/%d). Retrying in %ds …",
                        attempt,
                        config.MAX_API_RETRIES,
                        wait,
                    )
                    time.sleep(wait)
                else:
                    raise
        raise RuntimeError(
            f"API call {func.__name__} failed after "
            f"{config.MAX_API_RETRIES} retries."
        )
