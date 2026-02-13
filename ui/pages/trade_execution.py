"""
Trade Execution Page (Screen 3) - The Sniper Scope

Purpose: Detailed view before the trigger is pulled (pre-check screen).
Shows: Order breakdown, margin check, volume profile chart, place order buttons.
"""

import logging
from datetime import datetime, date

import streamlit as st
import plotly.graph_objects as go

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import config
from ui.app import get_kite_client, st
from ui.utils.data_utils import get_account_margins, get_quote, get_quotes
from analyst.analyst import analyze_stock

logger = logging.getLogger(__name__)


def render_volume_profile_chart(analysis: dict):
    """Render Volume Profile visualization using Plotly."""
    
    if not analysis or 'volume_profile' not in analysis:
        st.info("Volume profile data not available.")
        return
    
    vp = analysis['volume_profile']
    prices = vp.get('prices', [])
    volumes = vp.get('volumes', [])
    
    if not prices or not volumes:
        st.info("No volume profile data to display.")
        return
    
    # Find POC (Point of Control - max volume)
    max_vol_idx = volumes.index(max(volumes))
    poc_price = prices[max_vol_idx] if max_vol_idx < len(prices) else 0
    
    # Current price
    spot = analysis.get('spot_price', 0)
    
    # Create horizontal bar chart (Volume Profile)
    fig = go.Figure()
    
    # Volume Profile bars
    fig.add_trace(go.Bar(
        y=prices,
        x=volumes,
        orientation='h',
        marker_color='rgba(0, 100, 200, 0.6)',
        name='Volume'
    ))
    
    # Add POC line
    fig.add_vline(x=max(volumes), line_width=2, line_dash="dash", 
                  line_color="green", annotation_text="POC", annotation_position="top right")
    
    # Add current price line
    if spot > 0:
        fig.add_vline(x=0, line_width=3, line_color="red", 
                      annotation_text=f"Current: ₹{spot:,.0f}", annotation_position="top right")
    
    fig.update_layout(
        title="Volume Profile",
        xaxis_title="Volume",
        yaxis_title="Price (₹)",
        height=400,
        showlegend=False,
        yaxis=dict(autorange="reversed")  # Price increases going up
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_order_breakdown(candidate: dict, analysis: dict):
    """Render the order breakdown section."""
    
    st.markdown("### 📋 Order Breakdown")
    
    # Determine strategy
    is_bullish = candidate.get('trend') == 'Bullish'
    strategy = "BULL PUT SPREAD" if is_bullish else "BEAR CALL SPREAD"
    
    # Get strike details
    short_strike = analysis.get('short_strike', 0)
    long_strike = analysis.get('long_strike', 0)
    lot_size = analysis.get('lot_size', 0)
    
    # Get current premiums from quote
    kite = get_kite_client()
    short_premium = 0
    long_premium = 0
    
    if kite and short_strike > 0 and long_strike > 0:
        try:
            # Construct trading symbols
            # For now, we'll use a placeholder - in production, would get exact expiry
            st.info(f"Short Strike: {int(short_strike)} | Long Strike: {int(long_strike)}")
        except Exception as e:
            logger.warning(f"Could not fetch premiums: {e}")
    
    # Calculate net credit, max loss, breakeven
    # For Bull Put Spread: Sell higher strike PUT, Buy lower strike PUT
    # Net Credit = Short Premium - Long Premium
    # Max Loss = (Strike Difference * Lot Size) - Net Credit
    
    # Placeholder premiums (would be fetched from Kite)
    short_premium_placeholder = 45.0  # ₹45
    long_premium_placeholder = 20.0   # ₹20
    
    net_credit = short_premium_placeholder - long_premium_placeholder
    strike_diff = short_strike - long_strike
    max_loss = (strike_diff * lot_size) - (net_credit * lot_size)
    max_profit = net_credit * lot_size
    breakeven = short_strike - net_credit
    
    # Probability of Profit (simplified estimation)
    pop = 70  # Would be calculated from delta/probability
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Leg 1 (Short)")
        leg_type = "PE" if is_bullish else "CE"
        st.markdown(f"**SELL:** {int(short_strike)} {leg_type}")
        st.markdown(f"**Premium:** ₹{short_premium_placeholder:.2f}")
    
    with col2:
        st.markdown("#### Leg 2 (Long)")
        st.markdown(f"**BUY:** {int(long_strike)} {leg_type}")
        st.markdown(f"**Premium:** ₹{long_premium_placeholder:.2f}")
    
    st.divider()
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Net Credit",
            f"₹{net_credit:.2f}",
            help="Per lot. You receive this amount upfront."
        )
    
    with col2:
        st.metric(
            "Max Loss (Risk)",
            f"₹{max_loss:,.0f}",
            delta=f"Per lot",
            delta_color="inverse",
            help="If price goes against you beyond the long strike"
        )
    
    with col3:
        st.metric(
            "Breakeven",
            f"₹{breakeven:,.0f}",
            help="Price at which you start losing money"
        )
    
    with col4:
        st.metric(
            "Probability of Profit",
            f"~{pop}%",
            help="Estimated based on delta and historical price action"
        )


def render_margin_check(kite):
    """Render margin check section."""
    
    st.markdown("### 💰 Margin Check")
    
    if not kite:
        st.error("Not connected to Kite. Cannot verify margin.")
        return
    
    try:
        margins = get_account_margins(kite)
        
        # Required margin would be calculated from the spread
        # For now, use a placeholder
        required_margin = 28000  # ₹28,000 for a typical spread
        available = margins.get('available', 0)
        
        status = "✅ PASS" if available >= required_margin else "❌ FAIL"
        status_color = "green" if available >= required_margin else "red"
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Required", f"₹{required_margin:,}")
        
        with col2:
            st.metric("Available", f"₹{available:,.0f}")
        
        with col3:
            st.markdown(f"**Status:** <span style='color:{status_color}'>{status}</span>", 
                       unsafe_allow_html=True)
        
    except Exception as e:
        st.error(f"Failed to check margin: {e}")


def render_trade_actions(candidate: dict, analysis: dict):
    """Render trade execution buttons."""
    
    from executor.order_manager import OrderManager
    
    st.markdown("### 🎯 Trade Actions")
    
    col1, col2 = st.columns(2)
    
    trade_mode = st.session_state.trade_mode
    
    # Extract spread data from analysis
    if not analysis:
        st.warning("No analysis available. Please wait for analysis to complete.")
        return
    
    is_bullish = candidate.get('trend') == 'Bullish'
    strategy = "BULL_PUT" if is_bullish else "BEAR_CALL"
    leg_type = "PE" if is_bullish else "CE"
    
    # Build spread data for order manager
    short_strike = analysis.get('short_strike', 0)
    long_strike = analysis.get('long_strike', 0)
    lot_size = analysis.get('lot_size', 0)
    
    if short_strike == 0 or long_strike == 0 or lot_size == 0:
        st.warning("Invalid spread data. Please re-analyze the stock.")
        return
    
    # Get current premiums
    short_premium = analysis.get('short_premium', 45.0)
    long_premium = analysis.get('long_premium', 20.0)
    net_credit = short_premium - long_premium
    
    # Build spread dict for order manager
    spread = {
        "short_symbol": f"{candidate['symbol']}PE",  # Will be formatted by order manager
        "long_symbol": f"{candidate['symbol']}PE",
        "short_strike": short_strike,
        "long_strike": long_strike,
        "type": strategy,
        "lot_size": lot_size,
        "short_premium": short_premium,
        "long_premium": long_premium,
        "net_credit": net_credit,
        "sl_premium": short_premium * 2,  # SL at 100% of credit
        "target_premium": short_premium * 0.5,  # Target at 50% of credit
        "expiry": analysis.get('expiry', '')
    }
    
    with col1:
        market_btn = st.button(
            "📤 Place Market Order",
            use_container_width=True,
            type="primary",
            disabled=(trade_mode == "PAPER")
        )
        
        if market_btn:
            try:
                kite = get_kite_client()
                if not kite:
                    st.error("❌ Failed to connect to Kite. Please check your connection.")
                    return
                
                order_manager = OrderManager(kite)
                
                # Place the spread order (will use market price logic internally)
                success = order_manager.place_spread_order(
                    symbol=candidate['symbol'],
                    spread=spread,
                    is_paper=(trade_mode == "PAPER")
                )
                
                if success:
                    st.success("✅ Market order placed successfully!")
                    logger.info(f"Market order placed for {candidate['symbol']}")
                    st.rerun()
                else:
                    st.error("❌ Order placement failed. Check logs for details.")
                    logger.error(f"Market order failed for {candidate['symbol']}")
                    
            except Exception as e:
                logger.error(f"Market order exception: {e}")
                st.error(f"❌ Order placement error: {str(e)}")
    
    with col2:
        limit_btn = st.button(
            "📊 Place Limit Order (Mid-Price)",
            use_container_width=True,
            disabled=(trade_mode == "PAPER")
        )
        
        if limit_btn:
            try:
                kite = get_kite_client()
                if not kite:
                    st.error("❌ Failed to connect to Kite. Please check your connection.")
                    return
                
                # Calculate mid-price for limit order
                mid_price = (short_premium + long_premium) / 2
                
                order_manager = OrderManager(kite)
                
                # Modify spread for limit order with mid-price
                limit_spread = spread.copy()
                limit_spread["short_premium"] = mid_price * 0.95  # 5% buffer for limit sell
                limit_spread["long_premium"] = mid_price * 1.05   # 5% buffer for limit buy
                
                success = order_manager.place_spread_order(
                    symbol=candidate['symbol'],
                    spread=limit_spread,
                    is_paper=(trade_mode == "PAPER")
                )
                
                if success:
                    st.success(f"✅ Limit order placed at ₹{mid_price:.2f}!")
                    logger.info(f"Limit order placed for {candidate['symbol']} at ₹{mid_price:.2f}")
                    st.rerun()
                else:
                    st.error("❌ Order placement failed. Check logs for details.")
                    logger.error(f"Limit order failed for {candidate['symbol']}")
                    
            except Exception as e:
                logger.error(f"Limit order exception: {e}")
                st.error(f"❌ Order placement error: {str(e)}")
    
    if trade_mode == "PAPER":
        st.info("📝 Paper Trading Mode - Orders are simulated. Switch to LIVE mode to trade real money.")


def render_trade_execution():
    """Main trade execution render function."""
    
    st.title("🎯 Trade Execution")
    st.caption("Detailed view before pulling the trigger")
    
    # Check if a stock is selected
    candidate = st.session_state.get('selected_stock')
    
    if not candidate:
        st.warning("No stock selected. Please go to Scanner and click 'Load Trade' to select a stock.")
        
        # Show selection from recent scans
        if 'scan_results' in st.session_state and st.session_state.scan_results:
            st.markdown("#### Or select from recent scan results:")
            
            for result in st.session_state.scan_results[:3]:
                if st.button(f"Select {result['symbol']}", key=f"select_{result['symbol']}"):
                    st.session_state.selected_stock = result
                    st.rerun()
        return
    
    # Get analysis for the selected stock
    analysis = None
    try:
        kite = get_kite_client()
        if kite:
            with st.spinner(f"Analyzing {candidate['symbol']}..."):
                analysis = analyze_stock(kite, candidate['symbol'])
    except Exception as e:
        st.error(f"Analysis error: {e}")
        logger.error(f"Analysis error: {e}")
    
    # Header
    is_bullish = candidate.get('trend') == 'Bullish'
    strategy = "BULL PUT SPREAD" if is_bullish else "BEAR CALL SPREAD"
    
    st.markdown(f"## {candidate['symbol']} {strategy}")
    st.caption(f"IVP: {candidate.get('score', 0):.0f}% | Trend: {candidate.get('trend', 'Unknown')}")
    
    # Render sections
    with st.expander("📈 Volume Profile Chart", expanded=True):
        if analysis:
            render_volume_profile_chart(analysis)
        else:
            st.info("Volume profile analysis not available.")
    
    st.divider()
    
    if analysis:
        render_order_breakdown(candidate, analysis)
    else:
        st.info("Order breakdown not available.")
    
    st.divider()
    
    render_margin_check(get_kite_client())
    
    st.divider()
    
    render_trade_actions(candidate, analysis)


# Alias
render_trade_execution = render_trade_execution
