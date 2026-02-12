"""
IV Rank / IVP scoring engine.

Provides the core function ``get_iv_score()`` which evaluates each
F&O stock against two regimes:

    1. **IVP (IV Percentile)** — Used when ≥ 30 days of IV history
       exist in the database.
       Formula: IVP = (count of days where historic IV < today's IV) / total_days × 100

    2. **HV Rank (fallback)** — Used when < 30 days of IV history.
       Computes HV Rank from 1-year daily candles.
       Formula: HV_Rank = (current_HV − min_HV_1yr) / (max_HV_1yr − min_HV_1yr) × 100

Usage:
    from scanner.iv_scorer import get_iv_score

    score = get_iv_score("RELIANCE", current_iv=0.28, kite=kite)
    # score = {'method': 'IVP', 'score': 72.5, 'current_iv': 0.28}
"""

import logging

import config
from core.hv_calculator import calculate_hv, calculate_hv_series
from core.kite_client import KiteClient
from db.connection import get_connection

logger = logging.getLogger(__name__)


def _fetch_iv_history(symbol: str) -> list[float]:
    """
    Retrieve all historical IV values for a symbol from the database.

    Returns
    -------
    list[float]
        Chronologically ordered list of atm_iv values.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT atm_iv
            FROM iv_history
            WHERE stock_symbol = ?
            ORDER BY timestamp ASC
            """,
            (symbol,),
        ).fetchall()

    return [row[0] for row in rows]


def _fetch_latest_iv(symbol: str) -> float | None:
    """
    Get the most recent IV reading for a symbol.

    Returns
    -------
    float or None
        Latest atm_iv, or None if no records exist.
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT atm_iv
            FROM iv_history
            WHERE stock_symbol = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (symbol,),
        ).fetchone()

    return row[0] if row else None


def _calculate_ivp(iv_history: list[float], current_iv: float) -> float:
    """
    Compute IV Percentile.

    IVP = (number of days where historical IV < current IV) / total_days × 100

    Parameters
    ----------
    iv_history : list[float]
        All historical IV values (including today's).
    current_iv : float
        Today's IV value.

    Returns
    -------
    float
        IVP as a percentage (0–100).
    """
    count_lower = sum(1 for iv in iv_history if iv < current_iv)
    total = len(iv_history)

    if total == 0:
        return 0.0

    return round((count_lower / total) * 100, 2)


def _calculate_hv_rank(
    kite: KiteClient,
    symbol: str,
    nse_token: int | None = None,
) -> float | None:
    """
    Compute HV Rank from 1-year daily candle data.

    HV_Rank = (current_HV − min_HV) / (max_HV − min_HV) × 100

    Parameters
    ----------
    kite : KiteClient
        Authenticated Kite client.
    symbol : str
        Stock trading symbol (e.g. "RELIANCE").
    nse_token : int or None
        NSE instrument token. If None, cannot compute.

    Returns
    -------
    float or None
        HV Rank as a percentage (0–100), or None on failure.
    """
    if nse_token is None:
        logger.warning("No NSE token for %s — cannot compute HV Rank.", symbol)
        return None

    try:
        candles = kite.historical_data(nse_token, "day", 365)
        hv_series = calculate_hv_series(candles)

        if hv_series.empty or len(hv_series) < 2:
            logger.warning("Insufficient HV series data for %s.", symbol)
            return None

        current_hv = float(hv_series.iloc[-1])
        min_hv = float(hv_series.min())
        max_hv = float(hv_series.max())

        if max_hv == min_hv:
            return 50.0  # Flat vol — return neutral rank

        hv_rank = ((current_hv - min_hv) / (max_hv - min_hv)) * 100
        return round(hv_rank, 2)

    except Exception as exc:
        logger.error("HV Rank calculation failed for %s: %s", symbol, exc)
        return None


def get_iv_score(
    symbol: str,
    kite: KiteClient,
    current_iv: float | None = None,
    nse_token: int | None = None,
) -> dict | None:
    """
    Evaluate the IV score for a stock — IVP or HV Rank.

    Decision tree
    ^^^^^^^^^^^^^
    1. If ≥ IVP_MIN_DAYS (30) days of IV history exist → compute IVP.
    2. Otherwise → fallback to HV Rank from 1-year candle data.
    3. If both fail → return None (stock cannot be scored).

    Parameters
    ----------
    symbol : str
        F&O underlying symbol (e.g. "RELIANCE").
    kite : KiteClient
        Authenticated Kite client.
    current_iv : float or None
        Today's IV. If None, fetched from the database.
    nse_token : int or None
        NSE instrument token (needed for HV Rank fallback).

    Returns
    -------
    dict or None
        {
            'method': 'IVP' | 'HV_RANK',
            'score': float (0–100),
            'current_iv': float | None,
        }
        Returns None if scoring is not possible.
    """
    iv_history = _fetch_iv_history(symbol)

    # Resolve current_iv if not provided
    if current_iv is None:
        current_iv = _fetch_latest_iv(symbol)

    # ── Path 1: IVP (sufficient history) ──
    if len(iv_history) >= config.IVP_MIN_DAYS:
        if current_iv is None:
            logger.warning(
                "%s has %d days history but no current IV — skipping.",
                symbol,
                len(iv_history),
            )
            return None

        ivp = _calculate_ivp(iv_history, current_iv)
        logger.debug(
            "%s → IVP = %.1f%% (%d days of history)",
            symbol,
            ivp,
            len(iv_history),
        )
        return {
            "method": "IVP",
            "score": ivp,
            "current_iv": current_iv,
        }

    # ── Path 2: HV Rank (fallback) ──
    logger.debug(
        "%s has only %d days IV history — falling back to HV Rank.",
        symbol,
        len(iv_history),
    )
    hv_rank = _calculate_hv_rank(kite, symbol, nse_token)

    if hv_rank is None:
        return None

    return {
        "method": "HV_RANK",
        "score": hv_rank,
        "current_iv": current_iv,
    }
