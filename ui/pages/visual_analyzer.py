"""
Visual Analyzer Page (Screen 2) - The Visual Scanner

Purpose: Visualize the Stock Trend, Volume Profile Walls, and the proposed 
Strike Price in one interactive view with candlestick chart + Volume Profile overlay.

Features:
- Candlestick chart with Volume Profile overlay
- Symbol selector, lookback period, bin size controls
- Metrics bar (IV, IVP, Trend)
- Trade action panel (Approve & Execute, Skip Trade)

Based on UI_Phase-2.md PRD
"""

import logging
from datetime import datetime

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import config
from core.kite_client import KiteClient
from core.instrument_master import build_nse_token_map
from analyst.volume_profile import calculate_volume_profile, find_hvn_walls
from ui.app import get_kite_client

logger = logging.getLogger(__name__)


def fetch_historical_data(kite: KiteClient, symbol: str, days: int = 60):
    """
    Fetch historical OHLCV data for a given symbol.
    
    Parameters
    ----------
    kite : KiteClient
        Authenticated Kite client
    symbol : str
        Stock symbol (e.g., "RELIANCE")
    days : int
        Number of days of historical data to fetch
        
    Returns
    -------
    list[dict] or None
        List of candle dicts with keys: date, open, high, low, close, volume
    """
    try:
        # Build NSE token map
        token_map = build_nse_token_map(kite)
        
        # Get instrument token
        instrument_token = token_map.get(symbol)
        if not instrument_token:
            logger.error(f"Could not find instrument token for {symbol}")
            return None
        
        logger.info(f"Fetching {days} days of data for {symbol} (token: {instrument_token})")
        
        # Fetch historical data using the days parameter
        # Note: Kite API may have limits on how many days can be fetched at once
        # For daily data, typically max is around 60-90 days
        candles = kite.historical_data(
            instrument_token=instrument_token,
            interval="day",
            days=days
        )
        
        logger.info(f"Received {len(candles) if candles else 0} candles from API")
        
        # Transform to our format
        result = []
        for c in candles:
            # Log first candle to check data structure
            if len(result) == 0:
                logger.info(f"First candle structure: {c}")
            
            # Convert datetime to string for Plotly compatibility
            date_val = c.get("date", "")
            if hasattr(date_val, 'strftime'):
                # It's a datetime object, convert to string
                date_val = date_val.strftime("%Y-%m-%d")
            
            result.append({
                "date": date_val,
                "open": c.get("open", 0),
                "high": c.get("high", 0),
                "low": c.get("low", 0),
                "close": c.get("close", 0),
                "volume": c.get("volume", 0)
            })
        
        logger.info(f"Transformed {len(result)} candles")
        return result
        
    except Exception as e:
        logger.error(f"Error fetching historical data for {symbol}: {e}", exc_info=True)
        return None


def create_candlestick_with_volume_profile(
    candles: list[dict],
    volume_profile: dict,
    spot_price: float,
    short_strike: float | None = None,
    long_strike: float | None = None,
    bin_size: float = 10.0
):
    """
    Create a combined candlestick chart with Volume Profile overlay.
    
    Parameters
    ----------
    candles : list[dict]
        OHLCV data
    volume_profile : dict
        Output from calculate_volume_profile()
    spot_price : float
        Current market price
    short_strike : float or None
        Short strike price (for display)
    long_strike : float or None
        Long strike price (for display)
    bin_size : float
        Bin size used for volume profile
        
    Returns
    -------
    plotly.graph_objects.Figure
    """
    if not candles:
        return None
    
    # Check if we have valid volume profile data
    has_vp = volume_profile and volume_profile.get("bins") and len(volume_profile.get("bins", {})) > 0
    
    # Extract data and log for debugging
    dates = [c["date"] for c in candles]
    opens = [c["open"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    closes = [c["close"] for c in candles]
    volumes = [c["volume"] for c in candles]
    
    logger.info(f"Chart data extracted: {len(dates)} dates, {len(opens)} opens, {len(highs)} highs, {len(lows)} lows, {len(closes)} closes, {len(volumes)} volumes")
    logger.info(f"First date: {dates[0] if dates else 'None'}, Last date: {dates[-1] if dates else 'None'}")
    logger.info(f"Date types: {type(dates[0]) if dates else 'None'}")
    logger.info(f"First OHLC: O={opens[0] if opens else 0}, H={highs[0] if highs else 0}, L={lows[0] if lows else 0}, C={closes[0] if closes else 0}")
    
    # Volume Profile data
    vp_bins = volume_profile.get("bins", {})
    poc_price = volume_profile.get("poc", 0)
    va_high = volume_profile.get("va_high", 0)
    va_low = volume_profile.get("va_low", 0)
    
    # Prepare volume profile for horizontal bars
    # Sort by price and normalize volumes for display
    vp_prices = sorted(vp_bins.keys())
    vp_volumes = [vp_bins[p] for p in vp_prices]
    
    # Normalize volumes to fit nicely on the chart (scale to max volume)
    max_candle_vol = max(volumes) if volumes else 1
    max_vp_vol = max(vp_volumes) if vp_volumes else 1
    scale_factor = max_candle_vol / max_vp_vol if max_vp_vol > 0 else 1
    
    vp_volumes_scaled = [v * scale_factor * 0.3 for v in vp_volumes]  # 30% of candle volume
    
    # Create figure with 2 columns: left for candlesticks, right for volume profile
    # and 2 rows: top for price, bottom for volume
    fig = make_subplots(
        rows=2, cols=2,
        row_heights=[0.85, 0.15],
        column_widths=[0.85, 0.15],
        shared_yaxes=True,  # Share y-axis between candlesticks and volume profile
        shared_xaxes=True,  # Share x-axis between candlesticks and volume bars
        vertical_spacing=0.05,
        horizontal_spacing=0.02,
        specs=[
            [{"type": "candlestick"}, {"type": "bar"}],  # Row 1: candlesticks + volume profile
            [{"type": "bar", "colspan": 2}, None]  # Row 2: volume bars spanning both columns
        ]
    )
    
    # 1. Candlestick Chart (top-left)
    fig.add_trace(
        go.Candlestick(
            x=dates,
            open=opens,
            high=highs,
            low=lows,
            close=closes,
            name="Price",
            increasing_line_color="#26a69a",  # Green
            decreasing_line_color="#ef5350",  # Red
        ),
        row=1, col=1
    )
    
    # 2. Volume Profile (horizontal bars on right side) - only if we have VP data
    if has_vp:
        # Create horizontal bars showing volume at each price level
        # Use gradient colors based on volume intensity
        max_vp_vol = max(vp_volumes) if vp_volumes else 1
        
        # Create color gradient: blue (low) -> cyan -> green -> yellow -> red (high)
        bar_colors = []
        for vol in vp_volumes:
            ratio = vol / max_vp_vol
            if ratio < 0.25:
                # Blue to Cyan
                t = ratio / 0.25
                bar_colors.append(f'rgba(0, {int(t*255)}, 255, 0.7)')
            elif ratio < 0.5:
                # Cyan to Green
                t = (ratio - 0.25) / 0.25
                bar_colors.append(f'rgba(0, 255, {int(255*(1-t))}, 0.7)')
            elif ratio < 0.75:
                # Green to Yellow
                t = (ratio - 0.5) / 0.25
                bar_colors.append(f'rgba({int(t*255)}, 255, 0, 0.7)')
            else:
                # Yellow to Red
                t = (ratio - 0.75) / 0.25
                bar_colors.append(f'rgba(255, {int(255*(1-t))}, 0, 0.7)')
        
        fig.add_trace(
            go.Bar(
                y=vp_prices,
                x=vp_volumes,
                orientation='h',
                name='Volume Profile',
                marker_color=bar_colors,
                marker_line_color='rgba(255, 255, 255, 0.3)',
                marker_line_width=0.5,
                showlegend=True,
                hovertemplate='Price: ₹%{y:.0f}<br>Volume: %{x:,.0f}<extra></extra>'
            ),
            row=1, col=2
        )
        
        logger.info(f"Volume Profile bars added: {len(vp_prices)} bars")
        logger.info(f"VP price range: {min(vp_prices):.2f} - {max(vp_prices):.2f}")
        logger.info(f"VP volume range: {min(vp_volumes):.0f} - {max(vp_volumes):.0f}")
    
    # 3. Standard Volume Bars (bottom subplot)
    colors = ['#26a69a' if closes[i] >= opens[i] else '#ef5350' for i in range(len(closes))]
    fig.add_trace(
        go.Bar(
            x=dates,
            y=volumes,
            marker_color=colors,
            name='Volume',
            showlegend=False
        ),
        row=2, col=1
    )
    
    # 4. POC Line (Point of Control - highest volume node)
    if poc_price > 0:
        fig.add_hline(
            y=poc_price,
            line_dash="dash",
            line_color="orange",
            line_width=2,
            annotation_text=f"POC (₹{poc_price:,.0f})",
            annotation_position="right",
            row=1, col=1
        )
    
    # 5. Value Area Lines
    if va_high > 0:
        fig.add_hline(
            y=va_high,
            line_dash="dot",
            line_color="purple",
            line_width=1,
            annotation_text=f"VA High (₹{va_high:,.0f})",
            annotation_position="right",
            row=1, col=1
        )
    if va_low > 0:
        fig.add_hline(
            y=va_low,
            line_dash="dot",
            line_color="purple",
            line_width=1,
            annotation_text=f"VA Low (₹{va_low:,.0f})",
            annotation_position="right",
            row=1, col=1
        )
    
    # 6. Current Price Line
    if spot_price > 0:
        fig.add_hline(
            y=spot_price,
            line_dash="solid",
            line_color="red",
            line_width=2,
            annotation_text=f"Current (₹{spot_price:,.0f})",
            annotation_position="left",
            row=1, col=1
        )
    
    # 7. Short Strike Line (the strike we want to sell)
    if short_strike and short_strike > 0:
        fig.add_hline(
            y=short_strike,
            line_dash="solid",
            line_color="green",
            line_width=2,
            annotation_text=f"Short Strike (₹{short_strike:,.0f})",
            annotation_position="left",
            row=1, col=1
        )
    
    # 8. Long Strike Line (protection leg)
    if long_strike and long_strike > 0:
        fig.add_hline(
            y=long_strike,
            line_dash="dash",
            line_color="blue",
            line_width=2,
            annotation_text=f"Long Strike (₹{long_strike:,.0f})",
            annotation_position="left",
            row=1, col=1
        )
    
    # Layout updates
    fig.update_layout(
        title={
            'text': f"Volume Profile Analysis - Bin Size: ₹{bin_size}",
            'x': 0.5
        },
        xaxis_rangeslider_visible=False,
        height=700,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        hovermode="closest"
    )
    
    # Update y-axis titles
    # Left y-axis (candlesticks) - Price
    fig.update_yaxes(title_text="Price (₹)", row=1, col=1)
    # Right y-axis (volume profile) - no title, shared with left
    fig.update_yaxes(title_text="", row=1, col=2, showgrid=False)
    # Bottom subplot y-axis - Volume
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    
    # Update x-axis titles
    fig.update_xaxes(title_text="Date", row=2, col=1)
    fig.update_xaxes(title_text="Volume", row=1, col=2)
    
    # Set x-axis range for candlesticks to match the actual data range
    if dates:
        fig.update_xaxes(range=[dates[0], dates[-1]], row=1, col=1)
        fig.update_xaxes(range=[dates[0], dates[-1]], row=2, col=1)
    
    return fig


def calculate_strike_recommendation(
    volume_profile: dict,
    spot_price: float,
    trend: str = 'Unknown',
    iv_percentile: float = 0,
    min_otm_pct: float = 2.0,
    spread_width_pct: float = 2.0
) -> dict:
    """
    Calculate optimal strike prices for credit spreads based on Volume Profile.
    
    Based on Volume Profile Spread Strategy Guide:
    - Bullish trend → Bull Put Spread (short strike below HVN support)
    - Bearish trend → Bear Call Spread (short strike above HVN resistance)
    
    Parameters
    ----------
    volume_profile : dict
        Output from calculate_volume_profile()
    spot_price : float
        Current market price
    trend : str
        'Bullish', 'Bearish', or 'Unknown'
    iv_percentile : float
        IV percentile from scanner (0-100)
    min_otm_pct : float
        Minimum % OTM for short strike (default 2%)
    spread_width_pct : float
        Width of spread as % of underlying
        
    Returns
    -------
    dict
        Strike recommendation with rationale
    """
    if not volume_profile or not volume_profile.get('bins'):
        return None
    
    # Find HVN walls
    hvn_walls = find_hvn_walls(volume_profile, spot_price)
    support_wall = hvn_walls.get('support_wall')
    resistance_wall = hvn_walls.get('resistance_wall')
    all_hvns = hvn_walls.get('all_hvns', [])
    
    poc = volume_profile.get('poc', 0)
    vah = volume_profile.get('va_high', 0)
    val = volume_profile.get('va_low', 0)
    
    recommendation = {
        'trend': trend,
        'iv_percentile': iv_percentile,
        'spot_price': spot_price,
        'poc': poc,
        'vah': vah,
        'val': val,
        'support_wall': support_wall,
        'resistance_wall': resistance_wall,
        'all_hvns': all_hvns,
        'strategy_type': None,
        'short_strike': None,
        'long_strike': None,
        'volume_wall': None,
        'rationale': None
    }
    
    # Determine strategy based on trend
    if trend == 'Bullish':
        # Bull Put Spread: Find support below current price
        if support_wall:
            volume_wall = support_wall
            # Short strike: Below volume wall, min 2% OTM
            min_strike = spot_price * (1 - min_otm_pct / 100)
            short_strike = min(volume_wall * 0.98, min_strike)
        else:
            # Fallback to Value Area Low
            volume_wall = val if val > 0 else spot_price * 0.95
            short_strike = volume_wall * 0.98
        
        # Round to nearest 50 (typical strike interval)
        short_strike = round(short_strike / 50) * 50
        
        # Long strike: Spread width below short
        spread_width = spot_price * spread_width_pct / 100
        long_strike = short_strike - spread_width
        long_strike = round(long_strike / 50) * 50
        
        recommendation['strategy_type'] = 'Bull Put Spread'
        recommendation['short_strike'] = short_strike
        recommendation['long_strike'] = long_strike
        recommendation['volume_wall'] = volume_wall
        recommendation['rationale'] = f"Short strike placed below HVN support at ₹{volume_wall:.0f}"
        
    elif trend == 'Bearish':
        # Bear Call Spread: Find resistance above current price
        if resistance_wall:
            volume_wall = resistance_wall
            # Short strike: Above volume wall, min 2% OTM
            min_strike = spot_price * (1 + min_otm_pct / 100)
            short_strike = max(volume_wall * 1.02, min_strike)
        else:
            # Fallback to Value Area High
            volume_wall = vah if vah > 0 else spot_price * 1.05
            short_strike = volume_wall * 1.02
        
        # Round to nearest 50
        short_strike = round(short_strike / 50) * 50
        
        # Long strike: Spread width above short
        spread_width = spot_price * spread_width_pct / 100
        long_strike = short_strike + spread_width
        long_strike = round(long_strike / 50) * 50
        
        recommendation['strategy_type'] = 'Bear Call Spread'
        recommendation['short_strike'] = short_strike
        recommendation['long_strike'] = long_strike
        recommendation['volume_wall'] = volume_wall
        recommendation['rationale'] = f"Short strike placed above HVN resistance at ₹{volume_wall:.0f}"
    
    else:
        # Unknown trend - no recommendation
        recommendation['rationale'] = "Trend unknown. Run scanner to determine trend."
    
    return recommendation


def render_strike_recommendation(recommendation: dict):
    """Render the strike recommendation panel."""
    
    if not recommendation:
        st.info("No strike recommendation available. Run scanner first.")
        return
    
    st.markdown("### 🎯 Strike Recommendation")
    
    # Strategy type
    strategy = recommendation.get('strategy_type')
    if not strategy:
        st.warning(recommendation.get('rationale', 'No strategy available'))
        return
    
    # Strategy header
    strategy_color = "green" if "Put" in strategy else "red"
    st.markdown(f"**Strategy:** <span style='color:{strategy_color}'>{strategy}</span>", unsafe_allow_html=True)
    
    # Key levels
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Spot Price", f"₹{recommendation.get('spot_price', 0):,.0f}")
    
    with col2:
        st.metric("POC", f"₹{recommendation.get('poc', 0):,.0f}")
    
    with col3:
        wall = recommendation.get('volume_wall', 0)
        st.metric("Volume Wall", f"₹{wall:,.0f}" if wall else "N/A")
    
    st.divider()
    
    # Strike prices
    short_strike = recommendation.get('short_strike', 0)
    long_strike = recommendation.get('long_strike', 0)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Short Strike (Sell)")
        if "Put" in strategy:
            st.info(f"**SELL:** {int(short_strike)} PE")
        else:
            st.info(f"**SELL:** {int(short_strike)} CE")
        st.caption(f"Near Volume Wall: ₹{recommendation.get('volume_wall', 0):,.0f}")
    
    with col2:
        st.markdown("#### Long Strike (Buy)")
        if "Put" in strategy:
            st.info(f"**BUY:** {int(long_strike)} PE")
        else:
            st.info(f"**BUY:** {int(long_strike)} CE")
        st.caption("Protection leg")
    
    # Rationale
    st.divider()
    st.markdown(f"**Rationale:** {recommendation.get('rationale', 'N/A')}")
    
    # HVN levels
    all_hvns = recommendation.get('all_hvns', [])
    if all_hvns:
        with st.expander("📊 All HVN Levels"):
            st.markdown("**High Volume Nodes (Support/Resistance Walls):**")
            for hvn in sorted(all_hvns, reverse=True):
                distance = ((recommendation.get('spot_price', 0) - hvn) / recommendation.get('spot_price', 1)) * 100
                position = "above" if hvn > recommendation.get('spot_price', 0) else "below"
                st.markdown(f"- ₹{hvn:,.0f} ({position} spot by {abs(distance):.1f}%)")


def render_metrics_bar(candidate: dict, analysis: dict = None):
    """Render the metrics bar at the top of the page."""
    
    # Extract metrics
    iv = candidate.get('iv', 0)
    ivp = candidate.get('score', 0)  # IVP is stored as 'score' in candidates
    trend = candidate.get('trend', 'Unknown')
    spot = candidate.get('spot', 0)
    
    # Override with analysis data if available
    if analysis:
        iv = analysis.get('iv', iv)
        ivp = analysis.get('ivp', ivp)
        spot = analysis.get('spot_price', spot)
        if 'trend' not in candidate or candidate.get('trend') == 'Unknown':
            trend = analysis.get('trend', trend)
    
    # Trend emoji
    trend_emoji = "📈" if trend == "Bullish" else "📉" if trend == "Bearish" else "➡️"
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Current IV",
            f"{iv:.1f}%" if iv > 0 else "N/A",
            help="Implied Volatility"
        )
    
    with col2:
        st.metric(
            "IV Percentile",
            f"{ivp:.0f}%" if ivp > 0 else "N/A",
            help="IV Percentile - high values indicate elevated IV"
        )
    
    with col3:
        st.metric(
            "Spot Price",
            f"₹{spot:,.0f}" if spot > 0 else "N/A"
        )
    
    with col4:
        st.metric(
            "Trend",
            f"{trend} {trend_emoji}"
        )
    
    return spot, ivp, trend


def render_trade_action_panel(candidate: dict, analysis: dict):
    """Render the trade action panel with Approve/Skip buttons."""
    
    st.markdown("### 🎯 Trade Action Panel")
    
    # Get key information
    spot = analysis.get('spot_price', candidate.get('spot', 0))
    poc = analysis.get('poc', 0)
    short_strike = analysis.get('short_strike', 0)
    long_strike = analysis.get('long_strike', 0)
    trend = candidate.get('trend', 'Unknown')
    
    is_bullish = trend == "Bullish"
    leg_type = "PE" if is_bullish else "CE"
    
    # Detected opportunity text
    st.markdown("#### 📊 Detected Opportunity")
    
    if poc > 0 and spot > 0:
        if is_bullish:
            st.markdown(f"**Support Wall (POC):** ₹{poc:,.0f}")
            st.markdown(f"**Current Price:** ₹{spot:,.0f}")
            if short_strike > 0:
                st.success(f"💡 Selling **{int(short_strike)} {leg_type}** provides safety margin above support (POC: ₹{poc:,.0f})")
        else:
            st.markdown(f"**Resistance Wall (POC):** ₹{poc:,.0f}")
            st.markdown(f"**Current Price:** ₹{spot:,.0f}")
            if short_strike > 0:
                st.success(f"💡 Selling **{int(short_strike)} {leg_type}** provides safety margin below resistance (POC: ₹{poc:,.0f})")
    
    # Action buttons
    st.markdown("#### Choose Action")
    
    col1, col2 = st.columns(2)
    
    with col1:
        approve_btn = st.button(
            "✅ Approve & Execute",
            width="stretch",
            type="primary"
        )
        
        if approve_btn:
            # Store selected stock for trade execution
            st.session_state.selected_stock = candidate
            st.session_state.selected_analysis = analysis
            st.success(f"✅ Loaded {candidate['symbol']} for trade execution!")
            # Navigate to trade execution
            st.switch_page("?page=Trade Execution")
    
    with col2:
        skip_btn = st.button(
            "⏭️ Skip Trade",
            width="stretch"
        )
        
        if skip_btn:
            st.info(f"Skipped {candidate['symbol']}. Select another stock from the Scanner.")


def render_visual_analyzer():
    """Main visual analyzer render function."""
    
    st.title("📈 Visual Analyzer")
    st.caption("Interactive candlestick chart with Volume Profile overlay")
    
    # Initialize session state
    if 'visual_analyzer_symbol' not in st.session_state:
        st.session_state.visual_analyzer_symbol = None
    if 'visual_analyzer_days' not in st.session_state:
        st.session_state.visual_analyzer_days = 60
    if 'visual_analyzer_bin_size' not in st.session_state:
        st.session_state.visual_analyzer_bin_size = 10.0
    
    # Check for selected stock from scanner
    selected_from_scanner = st.session_state.get('selected_stock')
    
    # ──────────────────────────────────────────────
    # Header Controls
    # ──────────────────────────────────────────────
    st.markdown("### ⚙️ Controls")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        # Symbol selector
        if selected_from_scanner:
            # Use selected stock from scanner
            default_symbol = selected_from_scanner.get('symbol', 'RELIANCE')
            symbol = st.selectbox(
                "Select Symbol",
                options=[default_symbol],
                index=0,
                format_func=lambda x: x
            )
            st.session_state.visual_analyzer_symbol = symbol
        else:
            # Show common F&O stocks
            common_stocks = [
                "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
                "SBIN", "LT", "AXISBANK", "KOTAKBANK", "HINDUNILVR",
                "BHARTIARTL", "MARUTI", "BAJFINANCE", "TITAN", "ASIANPAINT"
            ]
            symbol = st.selectbox(
                "Select Symbol",
                options=common_stocks,
                index=0
            )
            st.session_state.visual_analyzer_symbol = symbol
    
    with col2:
        # Lookback period
        days = st.number_input(
            "Lookback Days",
            min_value=10,
            max_value=365,
            value=st.session_state.visual_analyzer_days,
            help="Number of days of historical data to fetch"
        )
        st.session_state.visual_analyzer_days = days
    
    with col3:
        # Bin size
        bin_size = st.number_input(
            "Bin Size (₹)",
            min_value=1.0,
            max_value=100.0,
            value=float(st.session_state.visual_analyzer_bin_size),
            step=1.0,
            help="Price bin width for Volume Profile calculation"
        )
        st.session_state.visual_analyzer_bin_size = bin_size
    
    st.divider()
    
    # ──────────────────────────────────────────────
    # Fetch Data and Analyze
    # ──────────────────────────────────────────────
    
    if not symbol:
        st.warning("Please select a symbol to analyze.")
        return
    
    # Get Kite client
    kite = get_kite_client()
    if not kite:
        st.error("Not connected to Kite. Please check your connection.")
        return
    
    # Fetch historical data
    with st.spinner(f"Fetching {days} days of data for {symbol}..."):
        candles = fetch_historical_data(kite, symbol, days)
    
    # Log the fetched data
    logger.info(f"=== Visual Analyzer Data for {symbol} ===")
    logger.info(f"Days requested: {days}")
    logger.info(f"Candles fetched: {len(candles) if candles else 0}")
    if candles:
        logger.info(f"Date range: {candles[0].get('date', 'N/A')} to {candles[-1].get('date', 'N/A')}")
        logger.info(f"First candle: O={candles[0].get('open', 0):.2f}, H={candles[0].get('high', 0):.2f}, L={candles[0].get('low', 0):.2f}, C={candles[0].get('close', 0):.2f}, V={candles[0].get('volume', 0)}")
        logger.info(f"Last candle:  O={candles[-1].get('open', 0):.2f}, H={candles[-1].get('high', 0):.2f}, L={candles[-1].get('low', 0):.2f}, C={candles[-1].get('close', 0):.2f}, V={candles[-1].get('volume', 0)}")
    
    if not candles:
        st.error(f"Could not fetch data for {symbol}. Please try another symbol.")
        return
    
    # Get current price (last close)
    spot_price = candles[-1]["close"] if candles else 0
    
    # Calculate volume profile
    with st.spinner("Calculating Volume Profile..."):
        volume_profile = calculate_volume_profile(candles, bin_size=bin_size)
    
    # Log volume profile results
    logger.info(f"=== Volume Profile ===")
    logger.info(f"Volume Profile calculated: {volume_profile is not None}")
    if volume_profile:
        vp_bins = volume_profile.get('bins', {})
        logger.info(f"VP bins count: {len(vp_bins)}")
        logger.info(f"POC: {volume_profile.get('poc', 0)}")
        logger.info(f"Value Area: {volume_profile.get('va_low', 0)} - {volume_profile.get('va_high', 0)}")
        logger.info(f"Bin size used: {volume_profile.get('bin_size', 0)}")
    
    # Debug: show what we got
    st.caption(f"DEBUG: candles={len(candles) if candles else 0}, volume_profile={type(volume_profile)}")
    
    # If volume profile calculation fails, create a simple one for display
    if not volume_profile:
        st.warning("⚠️ Volume Profile calculation failed (low volume or data issue). Showing candlestick chart only.")
        # Create a simple volume profile from candles
        volume_profile = {
            "bins": {},
            "poc": 0,
            "va_high": 0,
            "va_low": 0,
            "bin_size": bin_size
        }
    
    # Get analysis data (IV, IVP, strikes) - but don't invoke scanner
    # We'll get basic data from scanner results if available in session state
    analysis = None
    candidate = {"symbol": symbol, "spot": spot_price}
    
    # Check if we have analysis from scanner (don't re-run scanner)
    scan_results = st.session_state.get('scan_results', [])
    for result in scan_results:
        if result.get('symbol') == symbol:
            candidate['iv'] = result.get('iv', 0)
            candidate['ivp'] = result.get('ivp', 0)
            candidate['trend'] = result.get('trend', 'Unknown')
            candidate['score'] = result.get('score', 0)
            # Also check if analysis was cached
            analysis_cache = st.session_state.get('analysis_cache', {})
            analysis = analysis_cache.get(symbol)
            break
    
    # If no scanner results available, just use basic data without analysis
    if not candidate.get('iv'):
        candidate['iv'] = 0
        candidate['ivp'] = 0
        candidate['trend'] = 'Unknown'
        candidate['score'] = 0
    
    # ──────────────────────────────────────────────
    # Render Metrics Bar
    # ──────────────────────────────────────────────
    
    st.markdown("### 📊 Market Metrics")
    current_spot, current_ivp, current_trend = render_metrics_bar(candidate, analysis)
    
    st.divider()
    
    # ──────────────────────────────────────────────
    # Render Chart
    # ──────────────────────────────────────────────
    
    st.markdown("### 📈 Price & Volume Profile Chart")
    
    # Log chart creation attempt
    logger.info(f"=== Creating Chart ===")
    logger.info(f"Candles available: {len(candles) if candles else 0}")
    logger.info(f"Volume Profile available: {volume_profile is not None}")
    logger.info(f"Spot price: {spot_price}")
    
    # Calculate strike recommendation based on Volume Profile
    strike_recommendation = calculate_strike_recommendation(
        volume_profile=volume_profile,
        spot_price=spot_price,
        trend=candidate.get('trend', 'Unknown'),
        iv_percentile=candidate.get('ivp', 0)
    )
    
    # Get strikes from recommendation
    short_strike = strike_recommendation.get('short_strike', 0) if strike_recommendation else 0
    long_strike = strike_recommendation.get('long_strike', 0) if strike_recommendation else 0
    
    logger.info(f"Short strike: {short_strike}, Long strike: {long_strike}")
    
    # Create the combined chart
    try:
        logger.info(f"Calling create_candlestick_with_volume_profile with {len(candles)} candles")
        fig = create_candlestick_with_volume_profile(
            candles=candles,
            volume_profile=volume_profile,
            spot_price=spot_price,
            short_strike=short_strike,
            long_strike=long_strike,
            bin_size=bin_size
        )
        
        logger.info(f"Chart created: {fig is not None}")
        if fig:
            logger.info(f"Chart type: {type(fig)}")
            logger.info(f"Chart has {len(fig.data)} traces")
        
        if fig:
            logger.info("Rendering chart with st.plotly_chart...")
            st.plotly_chart(fig, width='stretch')
            logger.info("Chart rendered successfully")
        else:
            st.error("Could not create chart. Please try different parameters.")
            logger.error("Chart creation returned None")
    except Exception as e:
        st.error(f"Error creating chart: {e}")
        logger.error(f"Chart creation error: {e}", exc_info=True)
    
    st.divider()
    
    # ──────────────────────────────────────────────
    # Render Strike Recommendation
    # ──────────────────────────────────────────────
    
    render_strike_recommendation(strike_recommendation)
    
    st.divider()
    
    # ──────────────────────────────────────────────
    # Render Trade Action Panel
    # ──────────────────────────────────────────────
    
    if strike_recommendation and strike_recommendation.get('short_strike'):
        # Update candidate with strike info for trade action
        candidate['short_strike'] = strike_recommendation.get('short_strike')
        candidate['long_strike'] = strike_recommendation.get('long_strike')
        candidate['strategy_type'] = strike_recommendation.get('strategy_type')
        render_trade_action_panel(candidate, strike_recommendation)
    else:
        st.info("Run Scanner to get trend and IV data for strike recommendations.")


# Alias for use in app.py
render_visual_analyzer = render_visual_analyzer
