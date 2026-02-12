"""
Instrument Master — reusable F&O stock list and token lookups.

Provides shared functions for fetching and caching the NFO/NSE
instrument lists so callers (IV logger, scanner, executor) don't
each re-fetch independently.

Usage:
    from core.instrument_master import get_fno_stocks, build_nse_token_map
"""

import logging
from typing import Any

from core.kite_client import KiteClient

logger = logging.getLogger(__name__)


def get_fno_stocks(kite: KiteClient) -> list[dict[str, Any]]:
    """
    Return a deduplicated list of F&O equity underlying symbols.

    Filters NFO instruments for equity futures (segment='NFO-FUT',
    instrument_type='FUT') to derive the canonical list of underlyings.

    Returns
    -------
    list[dict]
        Each dict: {'symbol', 'exchange_token', 'instrument_token'}.
    """
    instruments = kite.instruments("NFO")
    seen: set[str] = set()
    fno_stocks: list[dict[str, Any]] = []

    for inst in instruments:
        name = inst.get("name", "")
        segment = inst.get("segment", "")
        instrument_type = inst.get("instrument_type", "")

        if segment == "NFO-FUT" and instrument_type == "FUT" and name not in seen:
            seen.add(name)
            fno_stocks.append(
                {
                    "symbol": name,
                    "exchange_token": inst["exchange_token"],
                    "instrument_token": inst["instrument_token"],
                }
            )

    logger.info("Instrument master: %d unique F&O underlyings.", len(fno_stocks))
    return fno_stocks


def build_nse_token_map(kite: KiteClient) -> dict[str, int]:
    """
    Build a {tradingsymbol → instrument_token} map for NSE equities.

    Used to look up the correct instrument token for historical-data
    and LTP calls on equity underlyings.
    """
    nse_instruments = kite.instruments("NSE")
    token_map: dict[str, int] = {}

    for inst in nse_instruments:
        if inst.get("segment") == "NSE":
            token_map[inst["tradingsymbol"]] = inst["instrument_token"]

    logger.info("NSE token map: %d symbols.", len(token_map))
    return token_map


def get_nfo_option_chain(
    kite: KiteClient,
    underlying: str,
) -> list[dict[str, Any]]:
    """
    Return all option instruments (CE + PE) for a given underlying.

    Useful for finding ATM/OTM strikes, building chains, etc.
    """
    instruments = kite.instruments("NFO")
    return [
        inst for inst in instruments
        if inst.get("name") == underlying
        and inst.get("instrument_type") in ("CE", "PE")
    ]
