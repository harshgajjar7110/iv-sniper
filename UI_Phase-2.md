This is the critical visual component of your bot. Traders trust charts, not just numbers. We need a solution that renders an interactive candlestick chart with a Volume Profile overlay without requiring you to write complex JavaScript.

### Analysis: The "Out of the Box" Charting Solution

**Recommendation: Plotly (Python Library)**
For a Python-based algo bot, **Plotly** is the undisputed winner for "out of the box" interactivity.
*   **Why:** It creates interactive, HTML-based charts natively in Python. It supports Candlesticks, Horizontal Bar Charts (for Volume Profile), and Shapes (for Strike markers) in a single figure.
*   **Integration:** It integrates seamlessly with Streamlit via `st.plotly_chart`.
*   **Alternative:** `mplfinance` is good for static images, but Plotly allows zooming/hovering, which is essential for analyzing "Key Areas."

---

### Data Gathering Logic (The Backend)

Before the UI can render, the backend must process the raw data.

**1. Data Inputs (from Zerodha API):**
*   **Instrument:** Stock Symbol (e.g., RELIANCE).
*   **Duration:** Last 60 Days.
*   **Interval:** Daily (for Positional Swing trades).

**2. The Volume Profile Algorithm (Pre-Processing):**
The chart needs two datasets:
*   **Dataset A (Candles):** Standard OHLC (Open, High, Low, Close).
*   **Dataset B (Profile):** Price vs. Volume Histogram.
    *   *Step 1: Binning.* Divide the price range into levels (e.g., Reliance ranges from 2400 to 2600. Create bins: 2400-2410, 2410-2420...).
    *   *Step 2: Distribution.* For every candle, assume volume is evenly distributed between High and Low. Add volume to the corresponding bins.
    *   *Step 3: Normalization.* Scale the volume numbers so the horizontal bars fit nicely on the chart axis.

---

### PRD: Screen 2 - The Visual Scanner (Detailed)

**Screen Name:** `Visual_Analyzer`
**Objective:** Visualize the Stock Trend, Volume Profile Walls, and the proposed Strike Price in one interactive view.

#### 1. UI Layout Specifications

**A. Header Section**
*   **Controls:**
    *   Symbol Selector (Dropdown: Auto-populated from Scanner Filter).
    *   Lookback Period (Slider: Default 60 days).
    *   Bin Size (Input: Default ₹10 for high priced stocks, ₹1 for low priced).
*   **Metrics Bar:**
    *   Current IV: `45.2` | IVP: `72` | Trend: `Bullish 📈`.

**B. The Main Chart Area (Plotly Implementation)**
*   **Subplot Grid:** 2 Rows.
    *   *Top Row (90% height):* Candlestick Chart + Volume Profile Overlay.
    *   *Bottom Row (10% height):* Standard Volume Bars (Red/Green).

*   **Visual Elements (The "Layers"):**
    1.  **Layer 1 (Base):** Candlestick Chart (Blue/Green candles).
    2.  **Layer 2 (Overlay):** Volume Profile (Horizontal Blue Bars on the right Y-Axis).
        *   **POC (Point of Control):** Highlight the thickest bar (High Volume Node) in **Orange**. This is your "Wall".
        *   **LVN (Low Volume Nodes):** Areas with thin bars (No man's land).
    3.  **Layer 3 (Annotation):**
        *   **Current Price Line:** Horizontal Dotted Red Line.
        *   **Proposed Strike Line:** Horizontal Solid Green Line (The strike the bot wants to sell).
        *   **Safety Net Line:** Horizontal Dashed Yellow Line (The "Buy" leg of the spread).

**C. Trade Action Panel (Below Chart)**
*   **Detected Opportunity:**
    *   "Detected Strong Support at **2420** (High Volume Node)."
    *   "Selling **2400 PE** provides safety margin above support."
*   **Buttons:**
    *   [Approve & Execute] (Green)
    *   [Skip Trade] (Grey)

#### 2. Technical Implementation Details (For Dev Agent)

**Libraries Required:**
`pandas`, `plotly.graph_objects`, `numpy`

**Visual Construction Logic:**
The chart is a combination of traces.

1.  **Candlesticks:** Standard `go.Candlestick`.
2.  **Volume Profile:** This is the trick.
    *   Use `go.Bar` with `orientation='h'` (Horizontal).
    *   X-axis = Volume.
    *   Y-axis = Price Levels (Bins).
    *   *Styling:* Set `opacity=0.5` and `marker_color='lightblue'` so it doesn't obscure the candles.
    *   *Alignment:* Align bars to the right side of the chart to act as a "Y-Axis Overlay".

**Code Snippet Logic (For PRD Reference):**

```python
import plotly.graph_objects as go

def create_chart_with_vp(df_candles, df_volume_profile, poc_price, strike_price):
    fig = go.Figure()

    # 1. Candlestick Trace
    fig.add_trace(go.Candlestick(
        x=df_candles['date'],
        open=df_candles['open'],
        high=df_candles['high'],
        low=df_candles['low'],
        close=df_candles['close'],
        name='Price'
    ))

    # 2. Volume Profile Trace (Horizontal Bars)
    # We use invisible X-axis for alignment or dual axis
    fig.add_trace(go.Bar(
        x=df_volume_profile['volume'], # The length of the bar
        y=df_volume_profile['price_level'], # The price level (Y-axis)
        orientation='h',
        name='Volume Profile',
        marker_color='rgba(0,100,255,0.3)', # Transparent Blue
        yaxis='y' # Align with Candlestick Y-axis
    ))

    # 3. Highlight POC (The Wall)
    fig.add_hline(
        y=poc_price,
        line_dash="dash",
        line_color="orange",
        annotation_text="POC (Support/Resistance Wall)",
        annotation_position="right"
    )

    # 4. Highlight Strike Selection
    fig.add_hline(
        y=strike_price,
        line_dash="dot",
        line_color="green",
        annotation_text="Selected Strike",
        annotation_position="left"
    )

    # Layout configuration
    fig.update_layout(
        title="Volume Profile Analysis",
        yaxis_title="Price",
        xaxis_title="Date / Volume",
        xaxis_rangeslider_visible=False # Cleaner view
    )
    
    return fig
```

#### 3. User Interaction Flow

1.  **User loads Screen 2.**
2.  **Bot auto-loads the first High IVP stock** (e.g., Reliance).
3.  **Chart Renders:**
    *   User sees the price candlesticks.
    *   User sees the horizontal blue bars (Volume Profile).
    *   **Insight:** User visually confirms that the "Orange Line (POC)" is indeed acting as Support.
    *   **Validation:** User sees the "Green Line (Strike)" is positioned safely above the "Orange Line."
4.  **Decision:** If the chart looks safe, user clicks **[Approve & Execute]**. If the chart looks choppy/risky, user clicks **[Skip Trade]**.

This approach gives you the "Out of the Box" feel of a professional terminal while relying entirely on Python logic for the backend.