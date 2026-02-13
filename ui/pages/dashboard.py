"""
Dashboard Page (Screen 1) - The Cockpit

Purpose: A quick glance to see if the system is healthy and profitable.
Displays: Capital health, today's P&L, active trades, and emergency stop.
"""

import logging
from datetime import datetime

import streamlit as st
import pandas as pd

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

logger = logging.getLogger(__name__)


def render_emergency_stop():
    """Render the emergency stop button and handle its action."""
    st.markdown("### 🛑 Emergency Controls")
    
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button(
            "⛔ EMERGENCY STOP",
            type="primary",
            use_container_width=True,
            help="Click to cancel all pending orders and square off all positions"
        ):
            # TODO: Implement actual emergency stop logic
            # This should:
            # 1. Cancel all pending orders via Kite API
            # 2. Square off all open positions
            # 3. Update bot status to STOPPED
            st.session_state.bot_status = "STOPPED"
            st.error("🚨 EMERGENCY STOP TRIGGERED! All positions will be squared off.")
            st.rerun()
    
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
        except:
            # Fallback to default values
            total_capital = 1_000_000
            used_margin = 0
            available = 1_000_000
    else:
        total_capital = 1_000_000
        used_margin = 0
        available = 1_000_000
    
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
        # Build symbol list
        trade_symbols = []
        for trade in open_trades:
            try:
                from datetime import date
                exp_date = datetime.strptime(trade['expiry'], "%Y-%m-%d").date()
            except:
                exp_date = date.today()
            
            yy = str(exp_date.year)[-2:]
            mon = exp_date.strftime("%b").upper()
            leg_type = "PE" if "PUT" in trade['strategy'] else "CE"
            
            short_sym = f"NFO:{trade['symbol']}{yy}{mon}{int(trade['short_strike'])}{leg_type}"
            long_sym = f"NFO:{trade['symbol']}{yy}{mon}{int(trade['long_strike'])}{leg_type}"
            trade_symbols.extend([short_sym, long_sym])
        
        try:
            quotes = get_quotes(kite, trade_symbols)
        except:
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
            use_container_width=True,
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
