"""
Scanner Page (Screen 2) - The Radar

Purpose: Visualize the output of the Scanner module.
Shows stocks filtered by IVP/HV and the calculated Volume Profile logic.

Features:
- Scanner settings (min IVP, min HV Rank)
- Opportunity cards with reasoning
- Load trade to execution
- View previous scan history
- Live logging with progress bar during scan
"""

import logging
import threading
import time
from datetime import datetime

import streamlit as st
import pandas as pd

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scanner.scanner import run_scan
from analyst.analyst import analyze_stock
from ui.app import get_kite_client, st

logger = logging.getLogger(__name__)


def render_scanner_settings():
    """Render scanner filter settings."""
    st.markdown("### ⚙️ Scanner Settings")
    
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        min_ivp = st.number_input(
            "Min IVP (%)",
            min_value=0,
            max_value=100,
            value=50,
            help="Minimum Implied Volatility Percentile to qualify"
        )
    
    with col2:
        min_hv_rank = st.number_input(
            "Min HV Rank (%)",
            min_value=0,
            max_value=100,
            value=50,
            help="Minimum Historical Volatility Rank to qualify (fallback when IVP < 30 days)"
        )
    
    with col3:
        refresh_btn = st.button(
            "🔄 Refresh Scanner",
            use_container_width=True,
            type="primary"
        )
    
    return min_ivp, min_hv_rank, refresh_btn


def render_scan_history():
    """Render scan history section to view previous scans."""
    st.markdown("### 📋 Scan History")
    
    try:
        from db.scan_store import get_all_scans, get_scan_result
        
        # Get list of recent scans
        scans = get_all_scans(limit=20)
        
        if not scans:
            st.info("No previous scans found. Run a scan to save results.")
            return None
        
        # Create a dropdown to select a scan
        scan_options = [
            f"{scan['scan_time'][:19]} - {scan['candidates_found']} candidates (IVP≥{scan['min_ivp']:.0f}%)"
            for scan in scans
        ]
        scan_options.insert(0, "-- Select a previous scan --")
        
        selected_idx = st.selectbox(
            "View previous scan results",
            range(len(scan_options)),
            format_func=lambda i: scan_options[i],
            key="scan_history_selector"
        )
        
        if selected_idx > 0:
            selected_scan = scans[selected_idx - 1]
            scan_id = selected_scan["scan_id"]
            
            # Get full scan details
            scan_detail = get_scan_result(scan_id)
            if scan_detail:
                st.markdown(f"""
                <div style="background-color: #e8f4f8; padding: 10px; border-radius: 5px; margin-bottom: 15px;">
                    <strong>Scan ID:</strong> {scan_id}<br>
                    <strong>Scanned:</strong> {scan_detail['total_scanned']} stocks<br>
                    <strong>Time:</strong> {scan_detail['scan_time'][:19]}<br>
                    <strong>Threshold:</strong> IVP ≥ {scan_detail['min_ivp']:.0f}%
                </div>
                """, unsafe_allow_html=True)
                return scan_detail["candidates"]
        
    except Exception as e:
        st.warning(f"Could not load scan history: {e}")
        logger.error(f"Error loading scan history: {e}")
    
    return None


def render_opportunity_card(candidate: dict, analysis: dict = None):
    """Render a single opportunity card with volume profile reasoning."""
    
    # Trend emoji
    trend_emoji = "📈" if candidate.get('trend') == 'Bullish' else "📉" if candidate.get('trend') == 'Bearish' else "➡️"
    
    # Score badge
    score = candidate.get('score', 0)
    score_badge = f"🟢 High" if score >= 70 else f"🟡 Medium" if score >= 50 else f"🔴 Low"
    
    # Strategy determination
    strategy = "BULL PUT SPREAD" if candidate.get('trend') == 'Bullish' else "BEAR CALL SPREAD"
    
    with st.container():
        # Header
        st.markdown(f"""
        <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 10px;">
            <h3 style="margin: 0; display: inline;">📊 {candidate['symbol']}</h3>
            <span style="float: right;">{score_badge} | IVP: {score:.0f}%</span>
            <div style="margin-top: 5px;">
                <strong>Trend:</strong> {candidate.get('trend', 'Unknown')} {trend_emoji}
                <span style="margin-left: 15px;"><strong>Strategy:</strong> {strategy}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Volume Profile Analysis
        if analysis:
            st.markdown("#### Volume Profile Analysis")
            
            col1, col2 = st.columns(2)
            
            with col1:
                spot = analysis.get('spot_price', candidate.get('spot', 0))
                st.metric("Current Price", f"₹{spot:,.0f}")
            
            with col2:
                poc = analysis.get('poc', 0)
                poc_strength = analysis.get('poc_strength', 'Medium')
                strength_emoji = "🟢" if poc_strength == "Strong" else "🟡" if poc_strength == "Medium" else "🔴"
                st.metric("Support Wall (POC)", f"₹{poc:,.0f}", delta=f"{strength_emoji} {poc_strength}")
            
            # Suggested Strikes
            st.markdown("##### Suggested Strikes")
            
            if candidate.get('trend') == 'Bullish':
                short_strike = analysis.get('short_strike', 0)
                long_strike = analysis.get('long_strike', 0)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.info(f"**SELL:** {int(short_strike)} PE (Near Support Wall)")
                with col2:
                    st.info(f"**BUY:** {int(long_strike)} PE (Protection)")
            else:
                short_strike = analysis.get('short_strike', 0)
                long_strike = analysis.get('long_strike', 0)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.info(f"**SELL:** {int(short_strike)} CE (Near Resistance Wall)")
                with col2:
                    st.info(f"**BUY:** {int(long_strike)} CE (Protection)")
            
            # Risk:Reward
            max_loss = analysis.get('max_loss', 0)
            max_profit = analysis.get('max_profit', 0)
            
            if max_loss > 0:
                reward_pct = (max_profit / max_loss) * 100 if max_loss > 0 else 0
                st.markdown(f"**Risk:Reward** → Risk ₹{max_loss:,.0f} for Reward ₹{max_profit:,.0f} ({reward_pct:.0f}%)")
        else:
            # Basic info when no analysis available
            st.markdown(f"**Current Price:** ₹{candidate.get('spot', 0):,.0f}")
            st.markdown(f"**IV Score:** {score:.0f}% ({candidate.get('method', 'N/A')})")
        
        # Action buttons
        st.markdown("##### Actions")
        
        col1, col2 = st.columns(2)
        
        with col1:
            view_chart_btn = st.button(
                f"📈 View Chart",
                key=f"chart_{candidate['symbol']}",
                use_container_width=True
            )
        
        with col2:
            load_trade_btn = st.button(
                f"🎯 Load Trade",
                key=f"load_{candidate['symbol']}",
                use_container_width=True,
                type="primary"
            )
            
            if load_trade_btn:
                # Store selected stock for trade execution
                st.session_state.selected_stock = candidate
                st.success(f"✅ Loaded {candidate['symbol']} for trade execution!")
        
        st.divider()


def render_scanner():
    """Main scanner render function."""
    
    st.title("🔍 Scanner")
    st.caption("Find high-probability credit spread opportunities")
    
    # Initialize session state for scan tracking
    # Add debug logging to diagnose initialization issue
    if 'scan_logs' not in st.session_state:
        st.session_state.scan_logs = []
        logger.info("DEBUG: Initialized scan_logs to empty list")
    else:
        logger.info(f"DEBUG: scan_logs already exists, length={len(st.session_state.scan_logs)}")
    
    if 'scan_in_progress' not in st.session_state:
        st.session_state.scan_in_progress = False
    if 'scan_results' not in st.session_state:
        st.session_state.scan_results = []
    if 'current_scan_id' not in st.session_state:
        st.session_state.current_scan_id = None
    if 'scan_progress' not in st.session_state:
        st.session_state.scan_progress = {"current": 0, "total": 0, "qualified": 0}
    if 'scan_error' not in st.session_state:
        st.session_state.scan_error = None
    # Cache for analysis results to avoid re-analyzing on each render
    if 'analysis_cache' not in st.session_state:
        st.session_state.analysis_cache = {}
    
    # Check if scan is in progress and display status
    if st.session_state.scan_in_progress:
        _display_scan_status()
        return  # Don't render the rest of the page while scanning
    
    # Check for scan error
    if st.session_state.scan_error:
        st.error(f"❌ Scan error: {st.session_state.scan_error}")
        st.session_state.scan_error = None
    
    # Create tabs for fresh scan and history
    tab1, tab2 = st.tabs(["🚀 Run Scan", "📋 Scan History"])
    
    with tab1:
        # Render settings and get values
        min_ivp, min_hv_rank, refresh_btn = render_scanner_settings()
        
        st.divider()
        
        # Show previous scan logs if available - use .get() for safety
        scan_logs = st.session_state.get('scan_logs', [])
        if scan_logs and not st.session_state.scan_in_progress:
            with st.expander("📋 Previous Scan Logs", expanded=False):
                st.code("\n".join(scan_logs[-30:]), language=None)
        
        # Run scan if refresh button clicked
        if refresh_btn:
            _run_scan_with_live_logs(min_ivp)
            st.rerun()  # Trigger rerun to show scan status
        
        # Display results
        results = st.session_state.scan_results
        
        if not results:
            st.info("No opportunities found. Click 'Refresh Scanner' to run the scan.")
            st.markdown("""
            **Tip:** The scanner looks for stocks with:
            - High IV Percentile (IVP > threshold)
            - Clear trend direction (Bullish/Bearish)
            - Good Volume Profile (Support/Resistance walls)
            """)
            return
        
        # Show scan ID if available
        if st.session_state.current_scan_id:
            st.markdown(f"**Current Scan ID:** `{st.session_state.current_scan_id}`")
        
        st.markdown(f"### 🎯 Opportunities Found: {len(results)}")
        
        # Render each opportunity - use cached analysis to avoid re-traversing
        analysis_cache = st.session_state.get('analysis_cache', {})
        for candidate in results:
            symbol = candidate['symbol']
            # Check if analysis is already cached
            analysis = analysis_cache.get(symbol)
            if analysis is None:
                # Only analyze if not cached
                try:
                    kite = get_kite_client()
                    if kite:
                        analysis = analyze_stock(kite, symbol)
                        # Cache the analysis result
                        if 'analysis_cache' not in st.session_state:
                            st.session_state.analysis_cache = {}
                        st.session_state.analysis_cache[symbol] = analysis
                except Exception as e:
                    logger.warning(f"Could not analyze {symbol}: {e}")
            
            render_opportunity_card(candidate, analysis)
    
    with tab2:
        # Show scan history
        historical_results = render_scan_history()
        
        if historical_results:
            st.markdown(f"### 🎯 Historical Opportunities: {len(historical_results)}")
            
            for candidate in historical_results:
                render_opportunity_card(candidate, analysis=None)


def _run_scan_with_live_logs(min_ivp: float) -> None:
    """
    Run the scanner with live logging display.
    
    Uses session state to track scan progress and auto-refresh to show updates.
    The scan runs in a background thread while the UI polls for updates.
    """
    # Initialize scan state in session state
    if 'scan_in_progress' not in st.session_state:
        st.session_state.scan_in_progress = False
    if 'scan_logs' not in st.session_state:
        st.session_state.scan_logs = []
    if 'scan_progress' not in st.session_state:
        st.session_state.scan_progress = {"current": 0, "total": 0, "qualified": 0}
    
    # If scan is already in progress, show status and return
    if st.session_state.scan_in_progress:
        st.info("⏳ A scan is already in progress. Please wait...")
        return
    
    # Get kite client
    kite = get_kite_client()
    if not kite:
        st.error("Not connected to Kite. Cannot run scanner.")
        return
    
    # Reset scan state (clear logs and cache for fresh scan)
    st.session_state.scan_in_progress = True
    st.session_state.scan_logs = []
    st.session_state.scan_progress = {"current": 0, "total": 0, "qualified": 0}
    st.session_state.scan_error = None
    st.session_state.analysis_cache = {}  # Clear cached analysis for new scan
    
    # Create thread-safe shared data structures for communication between threads
    # These will be accessed from the background thread and read by the main thread
    # REVIEW: This logic is quite complex and mixes UI state management with backend execution.
    # Consider extracting this into a dedicated 'ScanService' or similar to handle the background processing
    # and state synchronization, making the UI component cleaner and more testable.
    shared_logs = []
    shared_progress = {"current": 0, "total": 0, "qualified": 0}
    shared_results = {"results": None, "scan_id": None, "error": None, "done": False}
    lock = threading.Lock()
    
    def progress_callback(current: int, total: int, message: str, qualified: int) -> None:
        """Callback to update progress during scan - thread-safe."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        with lock:
            shared_logs.append(log_entry)
            shared_progress["current"] = current
            shared_progress["total"] = total
            shared_progress["qualified"] = qualified
    
    def run_scanner_thread():
        """Run the scanner in a background thread."""
        try:
            results, scan_id = run_scan(
                kite, 
                max_candidates=5, 
                min_score=min_ivp,
                progress_callback=progress_callback
            )
            with lock:
                shared_results["results"] = results
                shared_results["scan_id"] = scan_id
                shared_results["done"] = True
        except Exception as e:
            with lock:
                shared_results["error"] = str(e)
                shared_results["done"] = True
            logger.error(f"Scanner error: {e}")
    
    # Start scanner in background thread
    scanner_thread = threading.Thread(target=run_scanner_thread, daemon=True)
    scanner_thread.start()
    
    # Store shared data structures in session state for polling
    st.session_state.scan_shared_logs = shared_logs
    st.session_state.scan_shared_progress = shared_progress
    st.session_state.scan_shared_results = shared_results
    st.session_state.scan_lock = lock
    
    # Show initial status
    st.info("🔄 Starting scan... The page will refresh automatically.")


def _display_scan_status():
    """Display the current scan status if a scan is in progress."""
    if not st.session_state.get('scan_in_progress', False):
        return False
    
    # Sync shared data from background thread to session state (thread-safe)
    lock = st.session_state.get('scan_lock')
    if lock:
        with lock:
            # Copy shared data to session state for display
            shared_logs = st.session_state.get('scan_shared_logs', [])
            shared_progress = st.session_state.get('scan_shared_progress', {"current": 0, "total": 0, "qualified": 0})
            shared_results = st.session_state.get('scan_shared_results', {"results": None, "scan_id": None, "error": None, "done": False})
            
            # Update session state with latest data
            st.session_state.scan_logs = list(shared_logs)  # Create a copy
            st.session_state.scan_progress = dict(shared_progress)  # Create a copy
            
            # Check if scan is complete
            if shared_results["done"]:
                st.session_state.scan_in_progress = False
                if shared_results["error"]:
                    st.session_state.scan_error = shared_results["error"]
                else:
                    st.session_state.scan_results = shared_results["results"]
                    st.session_state.current_scan_id = shared_results["scan_id"]
                
                # Clean up shared data structures
                st.session_state.pop('scan_shared_logs', None)
                st.session_state.pop('scan_shared_progress', None)
                st.session_state.pop('scan_shared_results', None)
                st.session_state.pop('scan_lock', None)
                
                # Trigger rerun to show results
                st.rerun()
    
    # Create status container
    with st.status("🔄 Scanning F&O Universe...", expanded=True) as status:
        progress = st.session_state.get('scan_progress', {"current": 0, "total": 0, "qualified": 0})
        logs = st.session_state.get('scan_logs', [])
        
        # Progress bar
        if progress["total"] > 0:
            pct = int((progress["current"] / progress["total"]) * 100)
            st.progress(
                pct / 100.0, 
                text=f"{progress['current']}/{progress['total']} stocks ({pct}%) | {progress['qualified']} qualified"
            )
        else:
            st.progress(0, text="Initializing...")
        
        # Log display
        if logs:
            st.code("\n".join(logs[-30:]), language=None)
        
        # Auto-refresh while scan is in progress
        if st.session_state.get('scan_in_progress', False):
            time.sleep(0.5)
            st.rerun()
    
    return True


# Alias for use in app.py
render_scanner = render_scanner


# Alias for use in app.py
render_scanner = render_scanner




