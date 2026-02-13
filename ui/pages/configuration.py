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
from db.config_store import (
    save_int_setting, save_float_setting, save_bool_setting,
    load_int_setting, load_float_setting, load_bool_setting,
    load_all_settings
)

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
        # Save settings to database
        success1 = save_int_setting(
            "capital_risk_limit_pct",
            max_capital_per_trade,
            "Maximum percentage of capital to risk per trade"
        )
        success2 = save_int_setting(
            "max_total_usage_pct",
            max_total_usage,
            "Maximum percentage of capital to use across all trades"
        )
        
        if success1 and success2:
            st.success("✅ General settings saved successfully!")
            logger.info(f"General settings saved: risk={max_capital_per_trade}%, usage={max_total_usage}%")
        else:
            st.error("❌ Failed to save general settings.")


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
        # Save scanner settings to database
        success1 = save_int_setting(
            "hv_rank_threshold",
            iv_rank_threshold,
            "Minimum HV Rank % to qualify"
        )
        success2 = save_int_setting(
            "ivp_threshold",
            ivp_threshold,
            "Minimum IV Percentile to qualify"
        )
        success3 = save_int_setting(
            "min_days_to_expiry",
            min_days_to_expiry,
            "Minimum days to expiry to avoid weekly risk"
        )
        
        if success1 and success2 and success3:
            st.success("✅ Scanner settings saved successfully!")
            logger.info(f"Scanner settings saved: iv_rank={iv_rank_threshold}%, ivp={ivp_threshold}%, expiry_days={min_days_to_expiry}")
        else:
            st.error("❌ Failed to save scanner settings.")


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
        # Save exit rules to database
        success1 = save_int_setting(
            "profit_target_pct",
            profit_target_pct,
            "Exit when profit reaches this percentage of credit received"
        )
        success2 = save_float_setting(
            "stop_loss_multiplier",
            stop_loss_multiplier,
            "Exit when loss reaches this multiple of credit received"
        )
        success3 = save_bool_setting(
            "auto_square_off",
            auto_square_off,
            "Automatically square off when profit target is reached"
        )
        success4 = save_bool_setting(
            "force_exit_thursday",
            force_exit_thursday,
            "Square off all positions on Thursday 2:30 PM"
        )
        
        if success1 and success2 and success3 and success4:
            st.success("✅ Exit rules saved successfully!")
            logger.info(f"Exit rules saved: target={profit_target_pct}%, sl={stop_loss_multiplier}x, auto_sq={auto_square_off}, thu_exit={force_exit_thursday}")
        else:
            st.error("❌ Failed to save exit rules.")


def render_danger_zone():
    """Render danger zone with kill switches."""
    from ui.app import get_kite_client
    from ui.utils.data_utils import get_open_trades, get_quotes
    from watchdog.exits import ExitManager
    from datetime import datetime
    
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
            try:
                # Get Kite client
                kite = get_kite_client()
                
                if not kite:
                    st.error("❌ Failed to connect to Kite. Cannot execute kill switch.")
                else:
                    # Get open trades
                    open_trades = get_open_trades()
                    
                    if not open_trades:
                        st.info("No open positions to close.")
                    else:
                        # Build trade symbols
                        trade_symbols = []
                        for trade in open_trades:
                            try:
                                exp_date = datetime.strptime(trade['expiry'], "%Y-%m-%d").date()
                            except (ValueError, TypeError):
                                exp_date = datetime.now().date()
                            
                            yy = str(exp_date.year)[-2:]
                            mon = exp_date.strftime("%b").upper()
                            leg_type = "PE" if "PUT" in trade['strategy'] else "CE"
                            
                            short_sym = f"NFO:{trade['symbol']}{yy}{mon}{int(trade['short_strike'])}{leg_type}"
                            long_sym = f"NFO:{trade['symbol']}{yy}{mon}{int(trade['long_strike'])}{leg_type}"
                            trade_symbols.extend([short_sym, long_sym])
                        
                        # Fetch current quotes
                        quotes = get_quotes(kite, trade_symbols) if trade_symbols else {}
                        
                        # Close each trade
                        exit_manager = ExitManager(kite)
                        closed_count = 0
                        
                        for trade in open_trades:
                            try:
                                # Get current prices for the spread
                                trade_id = trade['trade_id']
                                syms = trade_symbols[trade_symbols.index(f"NFO:{trade['symbol']}{str(datetime.strptime(trade['expiry'], '%Y-%m-%d').date().year)[-2:]}{datetime.strptime(trade['expiry'], '%Y-%m-%d').date().strftime('%b').upper()}{int(trade['short_strike'])}{'PE' if 'PUT' in trade['strategy'] else 'CE'}"):]
                                
                                # Find the short and long symbols
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
                                    
                                    # Close the trade with MANUAL exit reason
                                    exit_manager.close_trade(trade, "MANUAL", short_ltp, long_ltp)
                                    closed_count += 1
                                    logger.info(f"Killed trade {trade_id} for {trade['symbol']}")
                            except Exception as e:
                                logger.error(f"Failed to close trade {trade.get('trade_id', 'unknown')}: {e}")
                        
                        st.session_state.bot_status = "STOPPED"
                        st.success(f"✅ Kill switch executed! Closed {closed_count} positions.")
                        logger.critical(f"KILL SWITCH TRIGGERED: {closed_count} positions closed")
                        st.rerun()
                        
            except Exception as e:
                logger.error(f"Kill switch failed: {e}")
                st.error(f"❌ Kill switch failed: {str(e)}")
    
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
