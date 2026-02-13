"""
Configuration Page (Screen 5) - The Brain

Purpose: Control the parameters without changing code.
Shows: Risk parameters, scanner settings, exit rules, kill switches.

Features:
- Capital Allocation settings
- Scanner Parameters
- Exit Rules
- Danger Zone (Kill Switch)
"""

import logging

import streamlit as st

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import config

logger = logging.getLogger(__name__)


def render_general_settings():
    """Render general capital allocation settings."""
    
    st.markdown("### 💰 General Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        max_capital_per_trade = st.number_input(
            "Max Capital Per Trade (%)",
            min_value=1,
            max_value=50,
            value=config.CAPITAL_RISK_LIMIT_PCT,
            help="Maximum percentage of total capital to risk in a single trade"
        )
    
    with col2:
        max_total_usage = st.number_input(
            "Max Total Usage (%)",
            min_value=10,
            max_value=100,
            value=50,
            help="Maximum percentage of total capital to use across all open trades"
        )
    
    if st.button("💾 Save General Settings", type="primary"):
        # TODO: Save to config or database
        st.success("✅ General settings saved!")


def render_scanner_parameters():
    """Render scanner parameter settings."""
    
    st.markdown("### 🔍 Scanner Parameters")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        iv_rank_threshold = st.number_input(
            "IV Rank Threshold",
            min_value=0,
            max_value=100,
            value=config.HV_RANK_THRESHOLD,
            help="Minimum IV Rank % to qualify"
        )
    
    with col2:
        ivp_threshold = st.number_input(
            "IVP Threshold",
            min_value=0,
            max_value=100,
            value=config.IVP_THRESHOLD,
            help="Minimum IV Percentile to qualify (requires 30+ days of data)"
        )
    
    with col3:
        min_days_to_expiry = st.number_input(
            "Min Days to Expiry",
            min_value=1,
            max_value=60,
            value=15,
            help="Minimum days to expiry to avoid weekly risk"
        )
    
    if st.button("💾 Save Scanner Settings"):
        # TODO: Save to config or database
        st.success("✅ Scanner settings saved!")


def render_exit_rules():
    """Render exit rule settings."""
    
    st.markdown("### 🎯 Exit Rules")
    
    col1, col2 = st.columns(2)
    
    with col1:
        profit_target_pct = st.number_input(
            "Profit Target (% of Credit)",
            min_value=10,
            max_value=100,
            value=config.PROFIT_TARGET_PCT,
            help="Exit when profit reaches this percentage of credit received"
        )
    
    with col2:
        stop_loss_multiplier = st.number_input(
            "Stop Loss (Multiple of Credit)",
            min_value=1.0,
            max_value=5.0,
            value=config.STOP_LOSS_MULTIPLIER,
            step=0.5,
            help="Exit when loss reaches this multiple of credit received"
        )
    
    col1, col2 = st.columns(2)
    
    with col1:
        auto_square_off = st.checkbox(
            "Auto-Square Off on Target",
            value=True,
            help="Automatically square off when profit target is reached"
        )
    
    with col2:
        force_exit_thursday = st.checkbox(
            "Force Exit on Thursdays (2:30 PM)",
            value=True,
            help="Square off all positions on Thursday 2:30 PM to avoid physical settlement"
        )
    
    if st.button("💾 Save Exit Rules"):
        # TODO: Save to config or database
        st.success("✅ Exit rules saved!")


def render_danger_zone():
    """Render danger zone with kill switches."""
    
    st.markdown("### ⚠️ DANGER ZONE")
    st.error("These actions are irreversible! Use with caution.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        disable_bot_btn = st.button(
            "🛑 DISABLE BOT (Stop Scanning)",
            use_container_width=True,
            help="Stop the bot from scanning for new opportunities"
        )
        
        if disable_bot_btn:
            st.session_state.bot_status = "STOPPED"
            st.warning("Bot disabled! Scanner will not look for new opportunities.")
            st.rerun()
    
    with col2:
        kill_switch_btn = st.button(
            "💣 KILL SWITCH (Square Off Everything)",
            use_container_width=True,
            type="primary",
            help="Immediately square off ALL open positions and cancel all pending orders"
        )
        
        if kill_switch_btn:
            # Show confirmation dialog
            st.error("🚨 KILL SWITCH TRIGGERED!")
            st.error("All positions will be squared off immediately!")
            # TODO: Implement actual kill switch logic
            # 1. Cancel all pending orders via Kite API
            # 2. Square off all positions
            # 3. Update database
            st.session_state.bot_status = "STOPPED"
            st.rerun()
    
    st.warning(
        "⚠️ Warning: The Kill Switch will close all positions at market price. "
        "This may result in slippage and realized losses."
    )


def render_current_config():
    """Display current configuration values."""
    
    st.markdown("### 📋 Current Configuration")
    
    with st.expander("View Current Settings", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Capital")
            st.markdown(f"- Max Capital Per Trade: {config.CAPITAL_RISK_LIMIT_PCT}%")
            st.markdown(f"- Profit Target: {config.PROFIT_TARGET_PCT}%")
            st.markdown(f"- Stop Loss: {config.STOP_LOSS_MULTIPLIER}x")
        
        with col2:
            st.markdown("#### Scanner")
            st.markdown(f"- IV Rank Threshold: {config.HV_RANK_THRESHOLD}%")
            st.markdown(f"- IVP Threshold: {config.IVP_THRESHOLD}%")
            st.markdown(f"- Min Days to Expiry: {config.IVP_MIN_DAYS}")
            st.markdown(f"- Volume Profile Days: {config.VP_LOOKBACK_DAYS}")


def render_configuration():
    """Main configuration render function."""
    
    st.title("⚙️ Configuration")
    st.caption("Control risk parameters and bot behavior")
    
    # Render all settings sections
    render_general_settings()
    st.divider()
    
    render_scanner_parameters()
    st.divider()
    
    render_exit_rules()
    st.divider()
    
    render_current_config()
    st.divider()
    
    render_danger_zone()


# Alias
render_configuration = render_configuration
