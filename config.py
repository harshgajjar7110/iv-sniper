"""
Configuration for IV-Sniper Bot.

SECURITY NOTE:
    Never commit real API keys to version control.
    All secrets are loaded from the .env file (gitignored).
    Run ``python auth_login.py`` to generate a fresh access token.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ──────────────────────────────────────────────
# Load .env (project root)
# ──────────────────────────────────────────────
_ENV_FILE = Path(__file__).resolve().parent / ".env"
load_dotenv(_ENV_FILE, override=True)

# ──────────────────────────────────────────────
# Zerodha Kite Connect Credentials
# ──────────────────────────────────────────────
KITE_API_KEY = os.getenv("KITE_API_KEY", "")
KITE_API_SECRET = os.getenv("KITE_API_SECRET", "")
KITE_ACCESS_TOKEN = os.getenv("KITE_ACCESS_TOKEN", "")

# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "iv_sniper.db"

# ──────────────────────────────────────────────
# Trading Parameters
# ──────────────────────────────────────────────
TRADING_DAYS_PER_YEAR = 252
HV_LOOKBACK_DAYS = 20               # Days for HV calculation (annualised)
IV_LOG_TIME = "15:25"                # Daily IV snapshot time (IST)
CAPITAL_RISK_LIMIT_PCT = 10          # Max % of capital per trade
PROFIT_TARGET_PCT = 50               # Exit at 50% of premium collected
STOP_LOSS_MULTIPLIER = 2.0           # Exit if premium doubles
EXPIRY_SQUARE_OFF_TIME = "14:30"     # Thursday safety square-off

# ──────────────────────────────────────────────
# Scanner Defaults
# ──────────────────────────────────────────────
IVP_MIN_DAYS = 30                    # Min IV history for IVP calc
HV_RANK_THRESHOLD = 50              # Min HV Rank % to qualify
IVP_THRESHOLD = 50                   # Min IVP % to qualify

# ──────────────────────────────────────────────
# Volume Profile (Chunk 3)
# ──────────────────────────────────────────────
VP_LOOKBACK_DAYS = 60                # Days of candles for VP calculation
VP_VALUE_AREA_PCT = 70               # Value Area accumulates this % of volume
VP_HVN_MULTIPLIER = 1.5             # HVN >= this × mean-bin-volume
VP_MIN_ADV = 500_000                 # Min Avg Daily Volume (skip dead stocks)

# ──────────────────────────────────────────────
# Spread Construction (Chunk 3)
# ──────────────────────────────────────────────
DEFAULT_SPREAD_WIDTH = 1             # Number of strikes for spread width
SPREAD_SL_PCT = 100                  # SL at 100% of credit (premium doubles)
SPREAD_TARGET_PCT = 50               # Target at 50% of credit collected

# ──────────────────────────────────────────────
# Safety & Rate Limiting
# ──────────────────────────────────────────────
MAX_API_RETRIES = 5
API_BACKOFF_BASE_SECONDS = 2         # Exponential backoff base
BID_ASK_SPREAD_LIMIT_PCT = 5         # Skip if spread > 5%
NIFTY_CRASH_THRESHOLD_PCT = 2        # Kill switch if Nifty down > 2%
