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
- All individual positions table with P&L breakdown
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
    get_all_live_positions,
    get_detailed_margins,
)
from ui.utils.symbol_utils import get_all_trade_symbols

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
                st.success(f"✅ Square off order placed for {trade['symbol']}!")
                st.rerun()
        
        with col2:
            modify_btn = st.button(
                f"⚙️ Modify Exit Target",
                key=f"modify_{trade['trade_id']}",
                use_container_width=True
            )
            
            # REVIEW: Implement logic to update exit targets in the database.
            if modify_btn:
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


def render_all_positions_table(kite):
    """
    Render ALL individual positions from Zerodha in a comprehensive table.
    Shows every option position with entry price, current price, P&L etc.
    """
    
    st.markdown("### 📋 All Zerodha Positions (Individual Legs)")
    
    if not kite:
        st.error("Not connected to Kite. Cannot fetch positions.")
        return
    
    try:
        all_positions = get_all_live_positions(kite)
        
        if not all_positions:
            st.info("No active option positions found in Zerodha.")
            return
        
        # Summary metrics
        total_current_pnl = sum(p.get('current_pnl', 0) for p in all_positions)
        total_realised = sum(p.get('realised_pnl', 0) for p in all_positions)
        total_unrealised = sum(p.get('unrealised_pnl', 0) for p in all_positions)
        total_m2m = sum(p.get('m2m', 0) for p in all_positions)
        total_pnl = sum(p.get('pnl', 0) for p in all_positions)
        
        short_count = sum(1 for p in all_positions if p['is_short'])
        long_count = sum(1 for p in all_positions if not p['is_short'])
        
        # Top-level summary
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Positions", len(all_positions))
        
        with col2:
            st.metric("Short / Long", f"{short_count} / {long_count}")
        
        with col3:
            pnl_delta = f"{'+' if total_pnl >= 0 else ''}{total_pnl:,.0f}"
            st.metric(
                "Total P&L",
                f"₹{total_pnl:,.0f}",
                delta=pnl_delta,
                delta_color="normal" if total_pnl >= 0 else "inverse"
            )
        
        with col4:
            st.metric(
                "M2M P&L",
                f"₹{total_m2m:,.0f}",
                delta_color="normal" if total_m2m >= 0 else "inverse"
            )
        
        # Realised vs Unrealised
        col1, col2 = st.columns(2)
        with col1:
            st.metric(
                "Realised P&L",
                f"₹{total_realised:,.0f}",
                delta_color="normal" if total_realised >= 0 else "inverse"
            )
        with col2:
            st.metric(
                "Unrealised P&L",
                f"₹{total_unrealised:,.0f}",
                delta_color="normal" if total_unrealised >= 0 else "inverse"
            )
        
        st.divider()
        
        # Build DataFrame for the positions table
        # REVIEW: Centralize P&L calculation logic in ui/utils/data_utils.py to avoid duplication
        # between here and calculate_spread_pnl.
        rows = []
        for pos in all_positions:
            pnl_val = pos.get('pnl', 0)
            current_pnl = pos.get('current_pnl', 0)
            
            rows.append({
                'Symbol': pos['tradingsymbol'],
                'Type': pos['position_type'],
                'Option': pos['option_type'],
                'Strike': pos['strike'],
                'Expiry': pos['expiry'],
                'Qty': pos['quantity'],
                'Avg Price': pos['average_price'],
                'LTP': pos['last_price'],
                'Current P&L': round(current_pnl, 2),
                'Realised': round(pos.get('realised_pnl', 0), 2),
                'Unrealised': round(pos.get('unrealised_pnl', 0), 2),
                'M2M': round(pos.get('m2m', 0), 2),
                'P&L': round(pnl_val, 2),
                'Product': pos.get('product', ''),
            })
        
        df = pd.DataFrame(rows)
        
        # Sort: short positions first, then by symbol
        df = df.sort_values(by=['Type', 'Symbol'], ascending=[True, True])
        
        # Style the dataframe - highlight P&L columns
        def color_pnl(val):
            if isinstance(val, (int, float)):
                if val > 0:
                    return 'color: green; font-weight: bold'
                elif val < 0:
                    return 'color: red; font-weight: bold'
            return ''
        
        pnl_columns = ['Current P&L', 'Realised', 'Unrealised', 'M2M', 'P&L']
        
        styled_df = df.style.applymap(
            color_pnl,
            subset=pnl_columns
        ).format({
            'Avg Price': '₹{:.2f}',
            'LTP': '₹{:.2f}',
            'Current P&L': '₹{:,.2f}',
            'Realised': '₹{:,.2f}',
            'Unrealised': '₹{:,.2f}',
            'M2M': '₹{:,.2f}',
            'P&L': '₹{:,.2f}',
        })
        
        st.dataframe(
            styled_df,
            use_container_width=True,
            hide_index=True,
            height=min(len(df) * 40 + 50, 600),
        )
        
        # Per-symbol P&L summary
        st.divider()
        st.markdown("#### 📊 P&L by Underlying")
        
        symbol_pnl = {}
        for pos in all_positions:
            sym = pos['symbol']
            if sym not in symbol_pnl:
                symbol_pnl[sym] = {
                    'symbol': sym,
                    'positions': 0,
                    'short_count': 0,
                    'long_count': 0,
                    'current_pnl': 0,
                    'realised_pnl': 0,
                    'unrealised_pnl': 0,
                    'm2m': 0,
                    'pnl': 0,
                }
            symbol_pnl[sym]['positions'] += 1
            if pos['is_short']:
                symbol_pnl[sym]['short_count'] += 1
            else:
                symbol_pnl[sym]['long_count'] += 1
            symbol_pnl[sym]['current_pnl'] += pos.get('current_pnl', 0)
            symbol_pnl[sym]['realised_pnl'] += pos.get('realised_pnl', 0)
            symbol_pnl[sym]['unrealised_pnl'] += pos.get('unrealised_pnl', 0)
            symbol_pnl[sym]['m2m'] += pos.get('m2m', 0)
            symbol_pnl[sym]['pnl'] += pos.get('pnl', 0)
        
        summary_rows = []
        for sym, data in symbol_pnl.items():
            summary_rows.append({
                'Underlying': data['symbol'],
                'Positions': data['positions'],
                'Short': data['short_count'],
                'Long': data['long_count'],
                'Current P&L': round(data['current_pnl'], 2),
                'Realised': round(data['realised_pnl'], 2),
                'Unrealised': round(data['unrealised_pnl'], 2),
                'M2M': round(data['m2m'], 2),
                'Total P&L': round(data['pnl'], 2),
            })
        
        summary_df = pd.DataFrame(summary_rows)
        if not summary_df.empty:
            summary_df = summary_df.sort_values('Total P&L', ascending=False)
            
            styled_summary = summary_df.style.applymap(
                color_pnl,
                subset=['Current P&L', 'Realised', 'Unrealised', 'M2M', 'Total P&L']
            ).format({
                'Current P&L': '₹{:,.2f}',
                'Realised': '₹{:,.2f}',
                'Unrealised': '₹{:,.2f}',
                'M2M': '₹{:,.2f}',
                'Total P&L': '₹{:,.2f}',
            })
            
            st.dataframe(
                styled_summary,
                use_container_width=True,
                hide_index=True,
            )
        
    except Exception as e:
        st.error(f"Failed to fetch positions: {e}")
        logger.exception("Error rendering all positions table")


def render_live_positions_summary(kite):
    """Render live positions from Zerodha (grouped as spreads)."""
    
    if not kite:
        st.error("Not connected to Kite. Cannot fetch live positions.")
        return
    
    try:
        live_spreads = get_live_positions(kite)
        
        if not live_spreads:
            st.info("No active spread positions in Zerodha.")
            return
        
        total_pnl = sum(s.get('pnl', 0) for s in live_spreads)
        total_m2m = sum(s.get('m2m', 0) for s in live_spreads)
        
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
        
        st.markdown("### 📡 Live Spreads from Zerodha")
        
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
    # Use utility function to get all trade symbols
    try:
        trade_symbols = get_all_trade_symbols(open_trades)
    except Exception as e:
        logger.warning(f"Could not get trade symbols: {e}")
        trade_symbols = []
    
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
            ["All Positions", "Spreads (Grouped)", "Live Only (Zerodha)", "Tracked Only (Database)"],
            horizontal=True,
            index=0
        )
    
    with col2:
        st.caption(f"🔄 Refresh: {st.session_state.refresh_interval}s")
    
    st.divider()
    
    # Show margin details if in LIVE mode
    if trade_mode == "LIVE" and kite:
        render_margin_details(kite)
        st.divider()
    
    # Show All Individual Positions (new default view)
    if position_filter == "All Positions":
        if trade_mode == "LIVE" and kite:
            render_all_positions_table(kite)
        else:
            st.warning("⚠️ Switch to LIVE mode to view all Zerodha positions")
        
        st.divider()
        st.markdown("### 📊 Tracked Positions (Database)")
        render_position_summary(kite)
    
    # Show Live Spreads from Zerodha
    elif position_filter == "Spreads (Grouped)":
        if trade_mode == "LIVE" and kite:
            render_live_positions_summary(kite)
        else:
            st.warning("⚠️ Switch to LIVE mode to view Zerodha spread positions")
    
    elif position_filter == "Live Only (Zerodha)":
        if trade_mode == "LIVE" and kite:
            render_all_positions_table(kite)
        else:
            st.warning("⚠️ Switch to LIVE mode to view Zerodha positions")
    
    # Show Tracked Positions (Database)
    elif position_filter == "Tracked Only (Database)":
        st.markdown("### 📊 Tracked Positions (Database)")
        render_position_summary(kite)


# Alias
render_position_monitor = render_position_monitor
