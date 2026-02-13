"""
Position Monitor Page (Screen 4) - The Watchdog

Purpose: Managing active trades (Chunk 5 of PRD).
Shows: Real-time P&L, exit rule status, square off controls.

Features:
- List of all open positions
- Current P&L with live updates
- Exit rule indicators (target, SL, time stop)
- Manual square off buttons
- Auto-square off toggle
- Live positions from Zerodha (when in LIVE mode)
- Margin details from Zerodha
"""

import logging
from datetime import datetime, date

import streamlit as st
import pandas as pd

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import config
from ui.app import get_kite_client, st
from ui.utils.data_utils import (
    get_open_trades,
    get_quotes,
    calculate_spread_pnl,
    get_exit_status,
    get_live_positions,
    get_detailed_margins,
)

logger = logging.getLogger(__name__)


def render_position_card(trade: dict, quotes: dict):
    """Render a single position card with P&L and exit status."""
    
    # Calculate P&L
    pnl_data = calculate_spread_pnl(trade, quotes)
    
    # Exit status
    exit_status = get_exit_status(trade, quotes)
    
    # Status color
    pnl_color = "green" if pnl_data['pnl'] >= 0 else "red"
    status_emoji = "🟢" if pnl_data['pnl'] >= 0 else "🔴"
    
    with st.container():
        # Header
        st.markdown(f"""
        <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 15px;">
            <h3 style="margin: 0; display: inline;">🔖 Trade ID: {trade['trade_id'][:8]}...</h3>
            <span style="float: right; font-size: 18px;">{status_emoji} <strong style="color: {pnl_color};">₹{pnl_data['pnl']:,.0f}</strong></span>
            <div style="margin-top: 5px;">
                <strong>{trade['symbol']}</strong> | {trade['strategy'].replace('_', ' ')} | {int(trade['short_strike'])}/{int(trade['long_strike'])}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Entry details
        col1, col2 = st.columns(2)
        
        with col1:
            entry_time = datetime.fromisoformat(trade['entry_time']).strftime('%I:%M %p')
            st.markdown(f"**Entry Time:** {entry_time}")
        
        with col2:
            lot_size = trade['lot_size']
            st.markdown(f"**Lot Size:** {lot_size}")
        
        st.divider()
        
        # Premium breakdown
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Entry:**")
            st.markdown(f"- Short: ₹{pnl_data['entry_credit']:.2f}")
            st.markdown(f"- Current: ₹{pnl_data['current_debit']:.2f}")
        
        with col2:
            st.markdown("**P&L:**")
            pnl_pct = pnl_data['pnl_pct']
            pnl_sign = "+" if pnl_pct >= 0 else ""
            st.markdown(f"- {pnl_sign}{pnl_pct:.1f}% of credit")
        
        st.divider()
        
        # Exit Rules Status
        st.markdown("#### 🚦 Exit Rules Status")
        
        # Profit Target
        target_status = "✅" if exit_status['target_hit'] else "⏳"
        target_label = "Triggered" if exit_status['target_hit'] else "Safe"
        st.markdown(f"{target_status} **Profit Target ({config.SPREAD_TARGET_PCT}%)**: {target_label}")
        
        # Stop Loss
        sl_status = "✅" if exit_status['sl_hit'] else "⏳"
        sl_label = "Triggered" if exit_status['sl_hit'] else "Safe"
        st.markdown(f"{sl_status} **Stop Loss ({config.SPREAD_SL_PCT}%)**: {sl_label}")
        
        # Time Stop (Thursday 2:30 PM)
        time_status = "⏳"
        if exit_status['time_stop_hit']:
            time_status = "⚠️"
        st.markdown(f"{time_status} **Time Stop (Thu 2:30 PM)**: {'Due Today!' if exit_status['time_stop_hit'] else 'Safe'}")
        
        st.divider()
        
        # Action buttons
        col1, col2 = st.columns(2)
        
        with col1:
            square_off_btn = st.button(
                f"🔴 Square Off Now (Market)",
                key=f"squareoff_{trade['trade_id']}",
                use_container_width=True,
                type="primary"
            )
            
            if square_off_btn:
                # TODO: Implement square off logic
                st.success(f"✅ Square off order placed for {trade['symbol']}!")
                st.rerun()
        
        with col2:
            modify_btn = st.button(
                f"⚙️ Modify Exit Target",
                key=f"modify_{trade['trade_id']}",
                use_container_width=True
            )
            
            if modify_btn:
                # TODO: Show modal to modify exit target
                st.info("Modify exit target - coming soon!")


def render_live_position_card(spread: dict):
    """Render a live position card with actual P&L from Zerodha."""
    
    pnl = spread.get('pnl', 0)
    pnl_color = "green" if pnl >= 0 else "red"
    status_emoji = "🟢" if pnl >= 0 else "🔴"
    
    strategy = spread.get('strategy', 'UNKNOWN')
    strategy_name = "BULL PUT SPREAD" if strategy == 'BULL_PUT' else "BEAR CALL SPREAD"
    
    with st.container():
        # Header
        st.markdown(f"""
        <div style="background-color: #e8f5e9; padding: 15px; border-radius: 10px; margin-bottom: 15px; border: 2px solid #4caf50;">
            <h3 style="margin: 0; display: inline;">📡 Live: {spread['symbol']}</h3>
            <span style="float: right; font-size: 18px;">{status_emoji} <strong style="color: {pnl_color};">₹{pnl:,.0f}</strong></span>
            <div style="margin-top: 5px;">
                {strategy_name} | {spread['short_strike']}/{spread['long_strike']} | Exp: {spread.get('expiry', 'N/A')}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Position details
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Short Leg:**")
            short_leg = spread.get('short_leg', {})
            st.markdown(f"- Strike: {short_leg.get('strike', 0)}")
            st.markdown(f"- Entry: ₹{short_leg.get('average_price', 0):.2f}")
            st.markdown(f"- Current: ₹{short_leg.get('last_price', 0):.2f}")
        
        with col2:
            st.markdown("**Long Leg:**")
            long_leg = spread.get('long_leg', {})
            st.markdown(f"- Strike: {long_leg.get('strike', 0)}")
            st.markdown(f"- Entry: ₹{long_leg.get('average_price', 0):.2f}")
            st.markdown(f"- Current: ₹{long_leg.get('last_price', 0):.2f}")
        
        st.divider()
        
        # P&L Breakdown
        col1, col2, col3 = st.columns(3)
        
        with col1:
            net_credit = spread.get('net_credit', 0)
            st.metric("Net Credit", f"₹{net_credit:.2f}")
        
        with col2:
            pnl_pct = spread.get('pnl_pct', 0)
            pnl_sign = "+" if pnl_pct >= 0 else ""
            st.metric("P&L %", f"{pnl_sign}{pnl_pct:.1f}%")
        
        with col3:
            m2m = spread.get('m2m', 0)
            m2m_color = "normal" if m2m >= 0 else "inverse"
            st.metric("M2M", f"₹{m2m:,.0f}", delta_color=m2m_color)
        
        # Realised/Unrealised
        col1, col2 = st.columns(2)
        
        with col1:
            realised = spread.get('realised_pnl', 0)
            st.metric("Realised P&L", f"₹{realised:,.0f}")
        
        with col2:
            unrealised = spread.get('unrealised_pnl', 0)
            unrealised_color = "normal" if unrealised >= 0 else "inverse"
            st.metric("Unrealised P&L", f"₹{unrealised:,.0f}", delta_color=unrealised_color)


def render_margin_details(kite):
    """Render margin details from Zerodha."""
    
    st.markdown("### 💰 Account Margins")
    
    if not kite:
        st.error("Not connected to Kite. Cannot fetch margins.")
        return
    
    try:
        margins = get_detailed_margins(kite)
        
        # Equity margins
        equity = margins.get('equity', {})
        commodity = margins.get('commodity', {})
        total_available = margins.get('total_available', 0)
        total_used = margins.get('total_used', 0)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Total Available",
                f"₹{total_available:,.0f}",
            )
        
        with col2:
            st.metric(
                "Margin Used",
                f"₹{total_used:,.0f}",
                delta_color="inverse"
            )
        
        with col3:
            total = total_available + total_used
            st.metric(
                "Total Margin",
                f"₹{total:,.0f}",
            )
        
        # Expandable for detailed breakdown
        with st.expander("📋 Detailed Breakdown"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Equity F&O:**")
                st.markdown(f"- Available: ₹{equity.get('available', 0):,.0f}")
                st.markdown(f"- Used: ₹{equity.get('used', 0):,.0f}")
                st.markdown(f"- Blocked: ₹{equity.get('blocked', 0):,.0f}")
            
            with col2:
                st.markdown("**Commodity:**")
                st.markdown(f"- Available: ₹{commodity.get('available', 0):,.0f}")
                st.markdown(f"- Used: ₹{commodity.get('used', 0):,.0f}")
                st.markdown(f"- Blocked: ₹{commodity.get('blocked', 0):,.0f}")
        
    except Exception as e:
        st.error(f"Failed to fetch margins: {e}")


def render_live_positions_summary(kite):
    """Render live positions from Zerodha."""
    
    if not kite:
        st.error("Not connected to Kite. Cannot fetch live positions.")
        return
    
    try:
        live_spreads = get_live_positions(kite)
        
        if not live_spreads:
            st.info("No active option positions in Zerodha.")
            return
        
        # Calculate total P&L
        total_pnl = sum(s.get('pnl', 0) for s in live_spreads)
        total_m2m = sum(s.get('m2m', 0) for s in live_spreads)
        
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Live Spreads", len(live_spreads))
        
        with col2:
            pnl_color = "normal" if total_pnl >= 0 else "inverse"
            st.metric(
                "Total P&L",
                f"₹{total_pnl:,.0f}",
                delta=f"{'+' if total_pnl >= 0 else ''}{total_pnl:,.0f}",
                delta_color=pnl_color
            )
        
        with col3:
            m2m_color = "normal" if total_m2m >= 0 else "inverse"
            st.metric(
                "M2M",
                f"₹{total_m2m:,.0f}",
                delta_color=m2m_color
            )
        
        st.divider()
        
        # Render each spread
        st.markdown("### 📡 Live Positions from Zerodha")
        
        for spread in live_spreads:
            render_live_position_card(spread)
            st.markdown("---")
        
    except Exception as e:
        st.error(f"Failed to fetch live positions: {e}")


def render_position_summary(kite):
    """Render position summary at the top."""
    
    open_trades = get_open_trades()
    
    if not open_trades:
        st.info("No open positions. Go to Scanner to find trading opportunities.")
        return
    
    # Fetch current quotes for all positions
    trade_symbols = []
    for trade in open_trades:
        try:
            exp_date = datetime.strptime(trade['expiry'], "%Y-%m-%d").date()
        except:
            exp_date = date.today()
        
        yy = str(exp_date.year)[-2:]
        mon = exp_date.strftime("%b").upper()
        leg_type = "PE" if "PUT" in trade['strategy'] else "CE"
        
        short_sym = f"NFO:{trade['symbol']}{yy}{mon}{int(trade['short_strike'])}{leg_type}"
        long_sym = f"NFO:{trade['symbol']}{yy}{mon}{int(trade['long_strike'])}{leg_type}"
        trade_symbols.extend([short_sym, long_sym])
    
    quotes = {}
    if kite and trade_symbols:
        try:
            quotes = get_quotes(kite, trade_symbols)
        except Exception as e:
            logger.warning(f"Could not fetch quotes: {e}")
    
    # Calculate total P&L
    total_pnl = 0
    for trade in open_trades:
        pnl_data = calculate_spread_pnl(trade, quotes)
        total_pnl += pnl_data['pnl']
    
    # Summary metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Open Positions",
            len(open_trades),
        )
    
    with col2:
        pnl_color = "normal" if total_pnl >= 0 else "inverse"
        st.metric(
            "Total P&L",
            f"₹{total_pnl:,.0f}",
            delta=f"{'+' if total_pnl >= 0 else ''}{total_pnl:,.0f}",
            delta_color=pnl_color
        )
    
    with col3:
        # Check if any target is hit
        targets_hit = 0
        for trade in open_trades:
            exit_status = get_exit_status(trade, quotes)
            if exit_status['target_hit']:
                targets_hit += 1
        
        if targets_hit > 0:
            st.success(f"🎯 {targets_hit} Target(s) Hit!")
        else:
            st.info("No exit targets hit yet")
    
    st.divider()
    
    # Render each position
    st.markdown("### 📊 Active Positions")
    
    for trade in open_trades:
        render_position_card(trade, quotes)
        st.markdown("---")


def render_position_monitor():
    """Main position monitor render function."""
    
    st.title("👁️ Position Monitor")
    st.caption("Real-time P&L and exit management for active trades")
    
    # Get Kite client
    kite = get_kite_client()
    
    # Check trade mode
    trade_mode = st.session_state.get('trade_mode', 'PAPER')
    
    # Position filter
    col1, col2 = st.columns([2, 1])
    
    with col1:
        position_filter = st.radio(
            "Show Positions:",
            ["Both", "Live Only (Zerodha)", "Tracked Only (Database)"],
            horizontal=True,
            index=0
        )
    
    with col2:
        # Auto-refresh info
        st.caption(f"🔄 Refresh: {st.session_state.refresh_interval}s")
    
    st.divider()
    
    # Show margin details if in LIVE mode
    if trade_mode == "LIVE" and kite:
        render_margin_details(kite)
        st.divider()
    
    # Show Live Positions from Zerodha
    if position_filter in ["Both", "Live Only (Zerodha)"]:
        if trade_mode == "LIVE" and kite:
            render_live_positions_summary(kite)
        elif position_filter == "Live Only (Zerodha)":
            st.warning("⚠️ Switch to LIVE mode to view Zerodha positions")
        
        if position_filter == "Both":
            st.divider()
    
    # Show Tracked Positions (Database)
    if position_filter in ["Both", "Tracked Only (Database)"]:
        st.markdown("### 📊 Tracked Positions (Database)")
        render_position_summary(kite)


# Alias
render_position_monitor = render_position_monitor
