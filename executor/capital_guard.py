"""
Capital and Risk Guards.

Ensures trades adhere to risk management rules:
- Margin Check: Required margin <= CAPITAL_RISK_LIMIT_PCT of total capital.
- Nifty Crash Guard: Stop if Nifty down > NIFTY_CRASH_THRESHOLD_PCT (2%).
- Bid-Ask Guard: Stop if spread > BID_ASK_SPREAD_LIMIT_PCT (5%).
"""

import logging
from typing import Any

from core.kite_client import KiteClient
import config

logger = logging.getLogger(__name__)


def check_nifty_crash(kite: KiteClient) -> bool:
    """
    Check if Nifty 50 is down more than the crash threshold.
    Returns False if crash detected (unsafe to trade), True otherwise.
    """
    try:
        # Nifty 50 symbol on NSE
        symbol = "NSE:NIFTY 50"
        quote = kite.quote([symbol]).get(symbol)
        
        if not quote:
            logger.warning("Could not fetch Nifty quote for crash check. Proceeding with caution.")
            return True

        ohlc = quote.get("ohlc", {})
        close = ohlc.get("close", 0)
        ltp = quote.get("last_price", 0)
        
        if close == 0:
            return True

        change_pct = ((ltp - close) / close) * 100
        
        if change_pct < -config.NIFTY_CRASH_THRESHOLD_PCT:
            logger.critical(
                "🚨 NIFTY CRASH DETECTED: Down %.2f%% (Threshold: %.1f%%). TRADING HALTED.",
                change_pct, config.NIFTY_CRASH_THRESHOLD_PCT
            )
            return False
        
        return True

    except Exception as e:
        logger.error("Error checking Nifty crash status: %s", e)
        # Fail safe: if we can't check market health, better to skip? 
        # Or assumes temporary API glitch. Let's warn and allow for now, 
        # as widespread failure would block unrelated trades.
        return True


def check_circuit_limits(symbol: str, quote: dict[str, Any]) -> bool:
    """
    Check if the stock has hit Upper or Lower Circuit limits.
    Returns True if safe (no circuit), False if circuit hit.
    """
    ltp = quote.get("last_price", 0)
    upper_circuit = quote.get("upper_circuit_limit", 0)
    lower_circuit = quote.get("lower_circuit_limit", 0)
    
    if ltp == 0:
        return False
        
    # Check limit hit (with tiny buffer for float precision? usually match exact)
    # If LTP >= Upper Circuit -> Buyer Freeze (Cannot Buy? No, usually Seller Freeze)
    # Upper Circuit = Only Buyers, No Sellers? 
    # Actually:
    # Upper Circuit: Price cannot go higher. Buyers available, no sellers.
    # Lower Circuit: Price cannot go lower. Sellers available, no buyers.
    # In both cases, liquidity is trapped.
    
    if upper_circuit > 0 and ltp >= upper_circuit:
        logger.warning(
            "Upper Circuit Hit for %s (LTP: %.2f, UC: %.2f). Liquidity risk. Skipping.",
            symbol, ltp, upper_circuit
        )
        return False
        
    if lower_circuit > 0 and ltp <= lower_circuit:
        logger.warning(
            "Lower Circuit Hit for %s (LTP: %.2f, LC: %.2f). Liquidity risk. Skipping.",
            symbol, ltp, lower_circuit
        )
        return False
        
    return True


def check_bid_ask_spread(
    symbol: str,
    bid: float,
    ask: float,
    ltp: float
) -> bool:
    """
    Check if bid-ask spread is within acceptable limits.
    Returns True if spread is okay, False if too wide.
    """
    if ltp == 0:
        return False
        
    spread = ask - bid
    spread_pct = (spread / ltp) * 100
    
    if spread_pct > config.BID_ASK_SPREAD_LIMIT_PCT:
        logger.warning(
            "Bid-Ask spread too wide for %s: %.2f%% (Limit: %.1f%%). Skipping.",
            symbol, spread_pct, config.BID_ASK_SPREAD_LIMIT_PCT
        )
        return False
        
    return True


def check_margin_and_capital(
    kite: KiteClient,
    orders: list[dict[str, Any]]
) -> bool:
    """
    Check if account has enough capital and trade consumes < 10% of total.
    
    orders: List of order dicts formatted for Kite basket_margins API.
    """
    try:
        # 1. Get available margins
        margins = kite.margins()
        equity = margins.get("equity", {})
        # 'net' is usually the available cash + collateral - used margin
        available_capital = equity.get("net", 0)
        
        if available_capital < config.MIN_CAPITAL_REQUIRED:
            logger.error(
                "Insufficient Capital: ₹%.2f < Min Required ₹%.2f",
                available_capital, config.MIN_CAPITAL_REQUIRED
            )
            return False

        # 2. Get required margin for the basket
        # Note: basket_margins might fail if one of the legs is invalid/illiquid
        try:
            basket_margins = kite.basket_margins(orders)
        except Exception as e:
            logger.error("Failed to calculate basket margins: %s", e)
            return False # Conservative: reject if we can't verify margin

        # 'initial' margin is what's required to open the position
        # 'total' includes exposure margin
        initial_margin = basket_margins.get("initial", {}).get("total", 0)
        
        # 3. Check against risk rules
        risk_limit = available_capital * (config.CAPITAL_RISK_LIMIT_PCT / 100.0)
        
        if initial_margin > risk_limit:
            logger.warning(
                "Margin Risk Exceeded: Required ₹%.2f > Limit ₹%.2f (10%% of ₹%.2f)",
                initial_margin, risk_limit, available_capital
            )
            return False
            
        logger.info(
            "Margin Check Passed: Required ₹%.2f (%.1f%% of capital)",
            initial_margin, (initial_margin / available_capital) * 100
        )
        return True

    except Exception as e:
        logger.error("Error in capital check: %s", e)
        return False
