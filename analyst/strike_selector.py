"""
Strike Selection & Spread Construction.

Maps Volume Profile walls to real tradeable option strikes from the
Kite instrument dump, then constructs a defined-risk credit spread.

Strategy
--------
- **Bullish trend** → Bull Put Spread (sell OTM put near support wall)
- **Bearish trend** → Bear Call Spread (sell OTM call near resistance wall)

Usage:
    from analyst.strike_selector import select_strikes, compute_spread_pnl

    strikes = select_strikes(
        wall_price=1820.0, spot=1870.0, trend="Bullish",
        option_chain=chain, nearest_monthly_expiry=expiry,
    )
    pnl = compute_spread_pnl(
        short_premium=45.0, long_premium=22.0,
        lot_size=50, spread_width=50.0,
    )
"""

import logging
from datetime import date, datetime
from typing import Any

import config

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Expiry helpers
# ──────────────────────────────────────────────

def find_nearest_monthly_expiry(option_chain: list[dict]) -> date | None:
    """
    Identify the nearest monthly expiry from an option chain.

    Monthly expiries in India fall on the last Thursday of the month.
    We find all unique expiries, identify which are month-end, and
    return the nearest future one.

    Parameters
    ----------
    option_chain : list[dict]
        NFO option instruments (from get_nfo_option_chain).

    Returns
    -------
    date or None
        The nearest monthly expiry date, or None if none found.
    """
    today = date.today()

    # Collect unique expiries
    expiries: set[date] = set()
    for inst in option_chain:
        exp = inst.get("expiry")
        if exp is None:
            continue
        if isinstance(exp, datetime):
            exp = exp.date()
        elif isinstance(exp, str):
            exp = datetime.fromisoformat(exp).date()
        if exp >= today:
            expiries.add(exp)

    if not expiries:
        return None

    # Identify monthly expiries (last Thursday of their month)
    monthly: list[date] = []
    for exp in sorted(expiries):
        if _is_last_thursday_of_month(exp, expiries):
            monthly.append(exp)

    if monthly:
        return monthly[0]  # nearest monthly

    # Fallback: if no clear monthly pattern, return the latest expiry
    # (handles edge cases where exchange adjusts for holidays)
    sorted_expiries = sorted(expiries)
    # Pick the first expiry that is ≥ 15 days out for decent theta
    for exp in sorted_expiries:
        if (exp - today).days >= 15:
            return exp

    # Last resort: just the nearest expiry
    return sorted_expiries[0] if sorted_expiries else None


def _is_last_thursday_of_month(
    exp: date,
    all_expiries: set[date],
) -> bool:
    """
    Check if an expiry is the last Thursday of its month.

    We also handle the case where the actual last Thursday is a holiday
    and the exchange shifts the expiry to Wednesday — by checking if
    no later expiry exists in the same month.
    """
    # Is it a Thursday (3) or Wednesday (2)?
    if exp.weekday() not in (2, 3):
        return False

    # Check there's no later expiry in the same year-month
    same_month_later = [
        e for e in all_expiries
        if e.year == exp.year and e.month == exp.month and e > exp
    ]
    return len(same_month_later) == 0


# ──────────────────────────────────────────────
# Strike Selection
# ──────────────────────────────────────────────

def select_strikes(
    wall_price: float,
    spot: float,
    trend: str,
    option_chain: list[dict],
    target_expiry: date | None = None,
    spread_width_strikes: int = config.DEFAULT_SPREAD_WIDTH,
) -> dict[str, Any] | None:
    """
    Select short and long strikes for a credit spread.

    Parameters
    ----------
    wall_price : float
        The VP support/resistance wall price level.
    spot : float
        Current market price of the underlying.
    trend : str
        "Bullish" or "Bearish" from the scanner.
    option_chain : list[dict]
        Full option chain from get_nfo_option_chain().
    target_expiry : date or None
        Which expiry to use. If None, auto-selects nearest monthly.
    spread_width_strikes : int
        Number of strikes for spread width (default: 1).

    Returns
    -------
    dict or None
        {
            'spread_type': 'BULL_PUT' | 'BEAR_CALL',
            'short_strike': float,
            'long_strike': float,
            'short_type': 'PE' | 'CE',
            'long_type': 'PE' | 'CE',
            'short_instrument': dict,
            'long_instrument': dict,
            'expiry': date,
            'lot_size': int,
        }
        Returns None if suitable strikes cannot be found.
    """
    # ── Determine expiry ──
    if target_expiry is None:
        target_expiry = find_nearest_monthly_expiry(option_chain)
    if target_expiry is None:
        logger.warning("No valid expiry found in option chain.")
        return None

    # ── Filter chain for target expiry ──
    expiry_chain = _filter_by_expiry(option_chain, target_expiry)
    if not expiry_chain:
        logger.warning("No instruments for expiry %s.", target_expiry)
        return None

    # ── Route by trend ──
    if trend == "Bullish":
        return _select_bull_put_spread(
            wall_price, spot, expiry_chain, target_expiry, spread_width_strikes
        )
    elif trend == "Bearish":
        return _select_bear_call_spread(
            wall_price, spot, expiry_chain, target_expiry, spread_width_strikes
        )
    else:
        logger.warning("Unknown trend '%s' — cannot select strikes.", trend)
        return None


def _filter_by_expiry(
    chain: list[dict],
    target_expiry: date,
) -> list[dict]:
    """Filter the option chain to only instruments matching the target expiry."""
    result = []
    for inst in chain:
        exp = inst.get("expiry")
        if exp is None:
            continue
        if isinstance(exp, datetime):
            exp = exp.date()
        if exp == target_expiry:
            result.append(inst)
    return result


def _select_bull_put_spread(
    support_wall: float,
    spot: float,
    chain: list[dict],
    expiry: date,
    spread_width: int,
) -> dict[str, Any] | None:
    """
    Bull Put Spread: SELL a put near support wall, BUY a lower put.

    Sell PE strike ≤ support_wall (OTM, below spot).
    Buy PE strike = next lower strike(s).
    """
    # Get all PE strikes, sorted descending
    puts = sorted(
        [i for i in chain if i.get("instrument_type") == "PE"],
        key=lambda i: i["strike"],
        reverse=True,
    )

    if not puts:
        logger.warning("No PE instruments in chain.")
        return None

    # Find the best short strike: highest PE strike that is ≤ support_wall AND < spot
    short_inst = None
    for inst in puts:
        if inst["strike"] <= support_wall and inst["strike"] < spot:
            short_inst = inst
            break

    if short_inst is None:
        # Fallback: nearest OTM put to support wall
        otm_puts = [i for i in puts if i["strike"] < spot]
        if not otm_puts:
            logger.warning("No OTM puts available below spot %.2f.", spot)
            return None
        # Find closest to support wall
        short_inst = min(otm_puts, key=lambda i: abs(i["strike"] - support_wall))

    short_strike = short_inst["strike"]

    # Long strike: the next lower strike(s) for protection
    lower_puts = sorted(
        [i for i in puts if i["strike"] < short_strike],
        key=lambda i: i["strike"],
        reverse=True,  # descending, so [0] is closest below
    )

    if len(lower_puts) < spread_width:
        logger.warning(
            "Not enough lower strikes for spread width %d below %.0f.",
            spread_width, short_strike,
        )
        return None

    long_inst = lower_puts[spread_width - 1]  # skip (spread_width - 1) strikes

    lot_size = short_inst.get("lot_size", 1)

    logger.info(
        "BULL PUT: Sell %s @ %.0f | Buy %s @ %.0f | Expiry: %s",
        short_inst["tradingsymbol"], short_strike,
        long_inst["tradingsymbol"], long_inst["strike"],
        expiry,
    )

    return {
        "spread_type": "BULL_PUT",
        "short_strike": short_strike,
        "long_strike": long_inst["strike"],
        "short_type": "PE",
        "long_type": "PE",
        "short_instrument": short_inst,
        "long_instrument": long_inst,
        "expiry": expiry,
        "lot_size": lot_size,
    }


def _select_bear_call_spread(
    resistance_wall: float,
    spot: float,
    chain: list[dict],
    expiry: date,
    spread_width: int,
) -> dict[str, Any] | None:
    """
    Bear Call Spread: SELL a call near resistance wall, BUY a higher call.

    Sell CE strike ≥ resistance_wall (OTM, above spot).
    Buy CE strike = next higher strike(s).
    """
    # Get all CE strikes, sorted ascending
    calls = sorted(
        [i for i in chain if i.get("instrument_type") == "CE"],
        key=lambda i: i["strike"],
    )

    if not calls:
        logger.warning("No CE instruments in chain.")
        return None

    # Find the best short strike: lowest CE strike that is ≥ resistance_wall AND > spot
    short_inst = None
    for inst in calls:
        if inst["strike"] >= resistance_wall and inst["strike"] > spot:
            short_inst = inst
            break

    if short_inst is None:
        # Fallback: nearest OTM call to resistance wall
        otm_calls = [i for i in calls if i["strike"] > spot]
        if not otm_calls:
            logger.warning("No OTM calls available above spot %.2f.", spot)
            return None
        short_inst = min(otm_calls, key=lambda i: abs(i["strike"] - resistance_wall))

    short_strike = short_inst["strike"]

    # Long strike: next higher strike(s) for protection
    higher_calls = sorted(
        [i for i in calls if i["strike"] > short_strike],
        key=lambda i: i["strike"],
    )

    if len(higher_calls) < spread_width:
        logger.warning(
            "Not enough higher strikes for spread width %d above %.0f.",
            spread_width, short_strike,
        )
        return None

    long_inst = higher_calls[spread_width - 1]

    lot_size = short_inst.get("lot_size", 1)

    logger.info(
        "BEAR CALL: Sell %s @ %.0f | Buy %s @ %.0f | Expiry: %s",
        short_inst["tradingsymbol"], short_strike,
        long_inst["tradingsymbol"], long_inst["strike"],
        expiry,
    )

    return {
        "spread_type": "BEAR_CALL",
        "short_strike": short_strike,
        "long_strike": long_inst["strike"],
        "short_type": "CE",
        "long_type": "CE",
        "short_instrument": short_inst,
        "long_instrument": long_inst,
        "expiry": expiry,
        "lot_size": lot_size,
    }


# ──────────────────────────────────────────────
# Spread P&L
# ──────────────────────────────────────────────

def compute_spread_pnl(
    short_premium: float,
    long_premium: float,
    lot_size: int,
    spread_width: float,
    sl_pct: float = config.SPREAD_SL_PCT,
    target_pct: float = config.SPREAD_TARGET_PCT,
) -> dict[str, Any]:
    """
    Calculate spread economics: max profit, max loss, SL level, target level.

    Parameters
    ----------
    short_premium : float
        Premium received for the sold option (per unit).
    long_premium : float
        Premium paid for the bought option (per unit).
    lot_size : int
        Number of units per lot.
    spread_width : float
        Absolute difference between short and long strikes.
    sl_pct : float
        Stop-loss as % of credit received (100 = exit when premium doubles).
    target_pct : float
        Profit target as % of credit (50 = exit at half premium).

    Returns
    -------
    dict
        {
            'net_credit': float,        — per-unit credit received
            'max_profit': float,        — net_credit × lot_size
            'max_loss': float,          — (spread_width - net_credit) × lot_size
            'risk_reward': float,       — max_profit / max_loss
            'breakeven': float,         — short_strike ± net_credit
            'sl_premium': float,        — exit when sold option hits this
            'target_premium': float,    — exit when sold option drops to this
            'sl_pct': float,
            'target_pct': float,
        }
    """
    net_credit = max(0.0, short_premium - long_premium)
    max_profit = net_credit * lot_size
    max_loss = (spread_width - net_credit) * lot_size

    risk_reward = round(max_profit / max_loss, 3) if max_loss > 0 else float("inf")

    # SL/Target levels (on the short option's premium)
    sl_premium = short_premium * (1 + sl_pct / 100.0)
    target_premium = short_premium * (1 - target_pct / 100.0)

    return {
        "net_credit": round(net_credit, 2),
        "max_profit": round(max_profit, 2),
        "max_loss": round(max_loss, 2),
        "risk_reward": risk_reward,
        "sl_premium": round(sl_premium, 2),
        "target_premium": round(max(0.0, target_premium), 2),
        "sl_pct": sl_pct,
        "target_pct": target_pct,
    }
