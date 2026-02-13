"""
Dashboard Page (Screen 1) - The Cockpit

Purpose: A quick glance to see if the system is healthy and profitable.
Displays: Capital health, today's P&L, active trades, and emergency stop.
"""

import logging
from datetime import datetime

import streamlit as st
import pandas as pd

import config
from ui.app import get_kite_client, st
from ui.utils.data_utils import (
    get_open_trades,
    get_today_trades,
    get_trade_statistics,
    get_account_margins,
    get_positions,
    get_quotes,
    calculate_spread_pnl,
)
from ui.utils.symbol_utils import get_all_trade_symbols

logger = logging.getLogger(__name__)


def render_emergency_stop():
    """Render the emergency stop button and handle its action."""
    st.markdown("### 🛑 Emergency Controls")
    
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button(
            "⛔ EMERGENCY STOP",
            type="primary",
            width="stretch",
            help="Click to cancel all pending orders and square off all positions"
        ):
            try:
                # Get Kite client
                kite = get_kite_client()
                
                if not kite:
                    st.error("❌ Failed to connect to Kite. Cannot execute emergency stop.")
                else:
                    # Get open trades
                    from ui.utils.data_utils import get_open_trades, get_quotes
                    open_trades = get_open_trades()
                    
                    if not open_trades:
                        st.info("No open positions to close.")
                    else:
                        # Use utility to get all trade symbols
                        from ui.utils.symbol_utils import get_all_trade_symbols
                        trade_symbols = get_all_trade_symbols(open_trades)
                        
                        # Fetch current quotes
                        quotes = get_quotes(kite, trade_symbols) if trade_symbols else {}
                        
                        # Close each trade
                        from position_watchdog.exits import ExitManager
                        exit_manager = ExitManager(kite)
                        closed_count = 0
                        
                        for trade in open_trades:
                            try:
                                # Find the short and long symbols for this trade
                                short_key = None
                                long_key = None
                                for sym in trade_symbols:
                                    if f"{trade['symbol']}" in sym and f"{int(trade['short_strike'])}" in sym:
                                        short_key = sym
                                    elif f"{trade['symbol']}" in sym and f"{int(trade['long_strike'])}" in sym:
                                        long_key = sym
                                
                                if short_key and long_key and short_key in quotes and long_key in quotes:
                                    short_ltp = quotes[short_key].get('last_price', 0)
                                    long_ltp = quotes[long_key].get('last_price', 0)
                                    
                                    # Close the trade
                                    exit_manager.close_trade(trade, "EMERGENCY", short_ltp, long_ltp)
                                    closed_count += 1
                                    logger.info(f"Emergency stop closed trade {trade.get('trade_id', 'unknown')} for {trade['symbol']}")
                            except Exception as e:
                                logger.error(f"Failed to close trade {trade.get('trade_id', 'unknown')}: {e}")
                        
                        st.session_state.bot_status = "STOPPED"
                        st.error(f"🚨 EMERGENCY STOP TRIGGERED! Closed {closed_count} positions.")
                        logger.critical(f"EMERGENCY STOP: {closed_count} positions closed")
                        st.rerun()
                        
            except Exception as e:
                logger.error(f"Emergency stop failed: {e}")
                st.error(f"❌ Emergency stop failed: {str(e)}")
    
    with col2:
        st.warning(
            "⚠️ Clicking this button will immediately cancel all pending orders "
            "and square off all open positions."
        )


def render_capital_health(kite):
    """Render the capital health section."""
    st.markdown("### 💰 Capital Health")
    
    # Try to get real margins from Kite, fallback to config
    if kite:
        try:
            margins = get_account_margins(kite)
            total_capital = margins.get('total', 0) + margins.get('used', 0)
            used_margin = margins.get('used', 0)
            available = margins.get('available', 0)
        except (KeyError, TypeError, AttributeError) as e:
            logger.warning(f"Failed to fetch margins from Kite: {e}. Using default values.")
            # Fallback to config values
            total_capital = config.TOTAL_CAPITAL
            used_margin = 0
            available = config.TOTAL_CAPITAL
    else:
        total_capital = config.TOTAL_CAPITAL
        used_margin = 0
        available = config.TOTAL_CAPITAL
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Total Capital",
            f"₹{total_capital:,.0f}",
        )
    
    with col2:
        st.metric(
            "Used Margin",
            f"₹{used_margin:,.0f}",
            delta=f"-₹{used_margin:,.0f}" if used_margin > 0 else None,
            delta_color="inverse"
        )
    
    with col3:
        st.metric(
            "Available",
            f"₹{available:,.0f}",
            delta=f"+₹{available:,.0f}" if available > 0 else None,
            delta_color="normal"
        )
    
    # Usage percentage
    if total_capital > 0:
        usage_pct = (used_margin / total_capital) * 100
        st.progress(min(usage_pct / 100, 1.0), text=f"Margin Usage: {usage_pct:.1f}%")


def render_today_performance():
    """Render today's performance metrics."""
    st.markdown("### 📊 Today's Performance")
    
    stats = get_trade_statistics()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        pnl = stats['today_pnl']
        delta_color = "normal" if pnl >= 0 else "inverse"
        st.metric(
            "Today's P&L",
            f"₹{pnl:,.0f}",
            delta=f"{'+' if pnl >= 0 else ''}{pnl:,.0f}",
            delta_color=delta_color
        )
    
    with col2:
        st.metric(
            "Trades Today",
            stats['today_trades'],
        )
    
    with col3:
        # Month-to-date win rate
        mtd_wins = stats['mtd_wins']
        mtd_trades = stats['mtd_trades']
        win_rate = (mtd_wins / mtd_trades * 100) if mtd_trades > 0 else 0
        st.metric(
            "Win Rate (MTD)",
            f"{win_rate:.0f}%",
            delta=f"{mtd_wins}/{mtd_trades} wins",
        )


def render_active_trades(kite):
    """Render the active trades table with real-time P&L."""
    st.markdown("### 📈 Active Trades")
    
    open_trades = get_open_trades()
    
    if not open_trades:
        st.info("No open trades at the moment. Go to Scanner to find opportunities.")
        return
    
    # Fetch current prices for P&L calculation
    if kite and open_trades:
        # Use utility function to get all trade symbols
        try:
            trade_symbols = get_all_trade_symbols(open_trades)
        except Exception as e:
            logger.warning(f"Failed to get trade symbols: {e}. Using empty list.")
            trade_symbols = []
        
        try:
            quotes = get_quotes(kite, trade_symbols)
        except (KeyError, TypeError, AttributeError) as e:
            logger.warning(f"Failed to fetch quotes: {e}. Using empty quotes.")
            quotes = {}
    else:
        quotes = {}
    
    # Build DataFrame
    data = []
    for trade in open_trades:
        pnl_data = calculate_spread_pnl(trade, quotes)
        
        # Status indicator
        if pnl_data['pnl'] > 0:
            status_emoji = "🟢"
            status_text = f"+{pnl_data['pnl_pct']:.0f}%"
        else:
            status_emoji = "🔴"
            status_text = f"{pnl_data['pnl_pct']:.0f}%"
        
        data.append({
            "Symbol": trade['symbol'],
            "Strategy": trade['strategy'].replace('_', ' '),
            "Entry Premium": f"₹{pnl_data['entry_credit']:.2f}",
            "Current Premium": f"₹{pnl_data['current_debit']:.2f}",
            "P&L": f"₹{pnl_data['pnl']:,.0f}",
            "Status": f"{status_emoji} {status_text}",
        })
    
    if data:
        df = pd.DataFrame(data)
        st.dataframe(
            df,
            width="stretch",
            hide_index=True
        )
    else:
        st.info("No active trades to display.")


def render_dashboard():
    """Main dashboard render function."""
    
    st.title("🎯 Dashboard")
    st.caption("System health check and quick overview")
    
    # Get Kite client
    kite = get_kite_client()
    
    # Render sections
    render_capital_health(kite)
    st.divider()
    
    render_today_performance()
    st.divider()
    
    render_active_trades(kite)
    st.divider()
    
    render_emergency_stop()
    
    # Auto-refresh note
    st.caption(
        f"🔄 Data auto-refreshes every {st.session_state.refresh_interval} seconds. "
        "Use the sidebar to adjust refresh rate."
    )
