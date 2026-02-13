"""
IV-Sniper UI - Main Application Entry Point

A Streamlit-based dashboard for the IV-Sniper algorithmic trading bot.
Provides real-time monitoring, trade execution, and configuration management.

Usage:
    streamlit run ui/app.py
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

import streamlit as st
from streamlit_autorefresh import st_autorefresh

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from core.kite_client import KiteClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Session State Initialization
# ──────────────────────────────────────────────

def init_session_state():
    """Initialize Streamlit session state variables."""
    # REVIEW: Consider moving session state initialization to a dedicated utility module (e.g., ui/utils/state_manager.py)
    # to keep app.py clean and centralized.
    
    # Bot status
    if 'bot_status' not in st.session_state:
        st.session_state.bot_status = 'STOPPED'  # RUNNING | STOPPED
    
    # Kite client (reuses existing connection)
    if 'kite_client' not in st.session_state:
        st.session_state.kite_client = None
    
    # Refresh interval for auto-refresh (in seconds)
    if 'refresh_interval' not in st.session_state:
        st.session_state.refresh_interval = 10
    
    # Selected stock for trade execution
    if 'selected_stock' not in st.session_state:
        st.session_state.selected_stock = None
    
    # Trade mode (PAPER | LIVE)
    if 'trade_mode' not in st.session_state:
        st.session_state.trade_mode = 'PAPER' if config.PAPER_TRADE_MODE else 'LIVE'
    
    # Last refresh timestamp
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = datetime.now()


def get_kite_client() -> KiteClient:
    """Get or create Kite client with proper error handling."""
    # REVIEW: Implement a retry mechanism or a more robust connection check here.
    # Also, consider caching the client instance or using a singleton pattern if not already handled by KiteClient.
    if st.session_state.kite_client is None:
        try:
            st.session_state.kite_client = KiteClient()
            # Validate connection
            st.session_state.kite_client.margins()
            logger.info("Kite client connected successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Kite: {e}")
            st.error(f"Failed to connect to Kite: {e}")
            return None
    return st.session_state.kite_client


# ──────────────────────────────────────────────
# Page Configuration
# ──────────────────────────────────────────────

st.set_page_config(
    page_title="IV-Sniper Bot",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ──────────────────────────────────────────────
# Sidebar Navigation
# ──────────────────────────────────────────────

def render_sidebar():
    """Render the sidebar with navigation and bot controls."""
    
    with st.sidebar:
        st.title("🎯 IV-Sniper Bot")
        
        # Bot Status Indicator
        status_color = "green" if st.session_state.bot_status == "RUNNING" else "red"
        status_icon = "●" if st.session_state.bot_status == "RUNNING" else "○"
        
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 20px;">
            <span style="font-size: 14px;">Status:</span>
            <span style="color: {status_color}; font-weight: bold;">
                {status_icon} {st.session_state.bot_status}
            </span>
        </div>
        """, unsafe_allow_html=True)
        
        # Navigation
        st.markdown("### 📍 Navigation")
        page = st.radio(
            "Go to",
            ["Dashboard", "Scanner", "Trade Execution", "Position Monitor", "Configuration"],
            label_visibility="collapsed"
        )
        
        st.divider()
        
        # Refresh Settings
        st.markdown("### ⚡ Auto-Refresh")
        st.session_state.refresh_interval = st.slider(
            "Refresh interval (seconds)",
            min_value=5,
            max_value=60,
            value=st.session_state.refresh_interval,
            step=5
        )
        
        st.divider()
        
        # Trade Mode
        st.markdown("### 💳 Trade Mode")
        trade_mode = st.radio(
            "Execution Mode",
            ["PAPER", "LIVE"],
            index=0 if st.session_state.trade_mode == "PAPER" else 1,
            horizontal=True
        )
        st.session_state.trade_mode = trade_mode
        
        if trade_mode == "LIVE":
            st.warning("⚠️ LIVE trading enabled - orders will be placed!")
        
        st.divider()
        
        # Connection Status
        st.markdown("### 🔌 Connection")
        kite = get_kite_client()
        if kite:
            st.success("✅ Connected to Kite")
        else:
            st.error("❌ Not connected to Kite")
        
        # Last refresh time
        st.caption(f"Last refresh: {st.session_state.last_refresh.strftime('%H:%M:%S')}")
    
    return page


# ──────────────────────────────────────────────
# Main Application
# ──────────────────────────────────────────────

def main():
    """Main application entry point."""
    
    # Initialize session state
    init_session_state()
    
    # Auto-refresh for real-time data (except on Configuration page)
    # Only auto-refresh on pages that need live data
    current_page_check = st.session_state.get('_current_page', 'Dashboard')
    if current_page_check != "Configuration":
        st_autorefresh(interval=st.session_state.refresh_interval * 1000, key="data_refresh")
    
    # Render sidebar and get current page
    current_page = render_sidebar()
    st.session_state['_current_page'] = current_page
    
    # Import pages dynamically to avoid loading all at once
    if current_page == "Dashboard":
        from pages.dashboard import render_dashboard
        render_dashboard()
    elif current_page == "Scanner":
        from pages.scanner import render_scanner
        render_scanner()
    elif current_page == "Trade Execution":
        from pages.trade_execution import render_trade_execution
        render_trade_execution()
    elif current_page == "Position Monitor":
        from pages.position_monitor import render_position_monitor
        render_position_monitor()
    elif current_page == "Configuration":
        from pages.configuration import render_configuration
        render_configuration()
    
    # Update last refresh time
    st.session_state.last_refresh = datetime.now()


if __name__ == "__main__":
    main()
