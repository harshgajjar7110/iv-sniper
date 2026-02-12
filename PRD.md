Product Requirement Document (PRD): IV-VP Credit Spread Bot
Project Code Name: IV-Sniper
Version: 1.0
Platform: Python (Backend), Zerodha Kite Connect (Execution/Data), SQLite (Storage).
Goal: Automate the identification of High IV/IVP stocks, locate key support/resistance via Volume Profile, and execute defined-risk Credit Spreads with automated exits.

System Architecture Overview
The system operates in five distinct stages:

Data Ingestion: Fetches historical stock data and maintains a local IV database.
Scanner: Filters the F&O universe for High IV Rank/IVP stocks.
Analyst: Calculates Volume Profile to find "Key Areas" (Walls).
Executor: Constructs and places Credit Spread orders on Zerodha.
Watchdog: Monitors open positions for 50% profit targets or Stop Losses.
Task Breakdown for Development Agent
Chunk 1: Infrastructure & Data Pipeline Setup
Objective: Establish connection to Zerodha, create the local database, and solve the "Historical IV" data gap.

Requirements:

Project Setup:
Initialize Python environment.
Install libraries: kiteconnect, pandas, numpy, scipy (for Black-Scholes), schedule (for cron jobs).
Create a secure config.py to store API Keys and Access Tokens.
Database Schema (SQLite):
Create table iv_history: (id, stock_symbol, timestamp, atm_iv, hv_20_day).
Create table trade_log: (id, trade_id, symbol, entry_time, exit_time, pnl, status).
Historical Volatility (HV) Calculator:
Write function calculate_hv(historical_candles).
Logic: Fetch 1-year daily candles. Calculate daily returns. Calculate Standard Deviation. Annualize (multiply by sqrt(252)).
The "IV Logger" Cron Job (Critical for IVP):
Create a script daily_iv_logger.py.
Logic:
Run every trading day at 3:25 PM.
Fetch ATM Option Price for all F&O stocks.
Calculate IV from Price using Black-Scholes function.
Save {Stock, Current_IV, Timestamp} to SQLite.
Note: This populates the database needed for IVP calculations in the future.
Deliverable: A Python script that successfully connects to Zerodha and saves daily IV data to a local file.

Chunk 2: The Scanner Module (The Filter)
Objective: Filter the list of 150+ F&O stocks to find 3-5 high-probability candidates.

Requirements:

Instrument Master:
Fetch the full instrument list from Kite.
Filter for NFO segment and F&O stocks. Clean the data to get a unique list of stock symbols.
IV Rank / IVP Logic:
Write function get_iv_score(stock_symbol).
Logic:
Check SQLite DB. If records < 30 days: Fallback to HV Rank.
Calculate HV Rank: (Current HV - Min HV_1Year) / (Max HV_1Year - Min HV_1Year).
If records >= 30 days: Calculate IVP.
Count how many days in history had IV lower than today's IV.
IVP = (Count_Lower / Total_Count) * 100.
Trend Detection:
Fetch 50-day EMA data.
Determine Trend: Bullish if Price > EMA, Bearish if Price < EMA.
Deliverable: A function that returns a list: [ {'symbol': 'RELIANCE', 'ivp': 75, 'trend': 'Bullish'} ].

Chunk 3: The Analyst Module (Volume Profile Strategy)
Objective: For the filtered stocks, calculate Volume Profile to identify Strike Prices.

Requirements:

Volume Profile Calculation:
Write function calculate_volume_profile(stock_symbol, days=60).
Fetch 60-day daily candles.
Logic: Iterate through candles, distribute volume across High-Low range into price bins (e.g., ₹5 or ₹10 bins).
Identify POC (Point of Control): The price bin with maximum volume.
Identify Value Area (VA): The range containing 70% of volume.
Strike Selection Logic:
Scenario A (Bullish Trend):
Identify Support_Wall (High Volume Node below current price).
Short Put Strike: Find OTM Put strike closest to Support_Wall.
Scenario B (Bearish Trend):
Identify Resistance_Wall (High Volume Node above current price).
Short Call Strike: Find OTM Call strike closest to Resistance_Wall.
Spread Construction:
Define Spread Width (e.g., next immediate strike).
Calculate Max Loss & Max Profit.
Deliverable: A JSON object specifying the exact Sell_Strike and Buy_Strike for the trade.

Chunk 4: The Execution Engine
Objective: Place the orders on Zerodha safely.

Requirements:

Capital Check:
Fetch Account Margin from Kite API.
Calculate Required Margin for the Spread (use Kite's Basket Margin API).
Hard Rule: If Required Margin > 10% of Total Capital -> Block Trade.
Order Placement:
Use Kite's place_order function.
Variety: kite.VARIETY_REGULAR.
Order Type: LIMIT. (Never Market).
Price Logic: Place Limit order at Mid-Price or slightly aggressive price to ensure fill.
Safety Triggers:
Tag orders with a tag (e.g., "IV_BOT") to identify bot trades later.
Write trade entry to trade_log database table.
Deliverable: A function that takes the JSON from Chunk 3 and successfully places the spread order on Kite.

Chunk 5: The Watchdog (Exit Logic)
Objective: Monitor open positions and exit based on the 50% rule or Stop Loss.

Requirements:

Position Monitor Loop:
Run every 5 minutes during market hours.
Fetch current positions using kite.positions().
Exit Condition 1: Profit Target (50% Rule):
Fetch current premium of the sold option (or the spread difference).
If Current Premium <= Entry Premium * 0.50:
Action: Square off position immediately.
Exit Condition 2: Stop Loss (2x Risk):
If Current Premium >= Entry Premium * 2.0 (or defined risk level):
Action: Square off position immediately.
Exit Condition 3: Expiry Safety (Thursday Rule):
If Day == Thursday AND Time > 2:30 PM:
Action: Square off ALL bot positions. (Avoid Physical Settlement).
Deliverable: A script bot_monitor.py that runs in the background and handles exits automatically.

Error Handling & Edge Cases (Must Implement)
API Rate Limits: If Zerodha returns error "Rate Limit Exceeded", implement exponential backoff (sleep and retry).
Wide Bid-Ask Spreads: If (Ask - Bid) > 5% of Price, skip the trade. Entering at a bad price destroys the edge.
Circuit Limits: If a stock hits Upper/Lower Circuit, disable the bot for that stock (liquidity dries up).
Black Swan: Hard-coded Kill Switch. If Nifty drops > 2% in a day, stop selling Put Spreads.
Summary for Developer Agent
Start with Chunk 1: Focus on the database and Zerodha connection. Do not proceed until you can reliably save IV data daily.
Use HV Rank initially: Since you have no IV history yet, use HV Rank (from 1-year stock data) as your primary filter for the first 1-2 months.
Volume Profile: Implement the distribution logic carefully. It is the mathematical key to your "Support/Resistance" logic.
Safety First: The 10% Capital rule and Thursday 2:30 PM square-off are non-negotiable features.