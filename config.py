"""
config.py — Global configuration for XAUUSD Research Platform.
Loads environment variables and exposes constants used platform-wide.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# ── API Keys ───────────────────────────────────────────────────────────────────
ALLTICK_API_KEY: str = os.getenv("ALLTICK_API_KEY", "")
FRED_API_KEY: str = os.getenv("FRED_API_KEY", "")
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# ── Cache paths ────────────────────────────────────────────────────────────────
CACHE_DIR = BASE_DIR / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── Signal weights (must sum to 100) ──────────────────────────────────────────
SIGNAL_WEIGHTS = {
    "dfii10": 30,   # Real yield (10-yr TIPS)
    "dxy":    25,   # DXY 20-day trend
    "cot":    25,   # COT Managed Money net
    "max_pain": 20, # CME OI Max Pain distance
}

# ── Directional score thresholds ──────────────────────────────────────────────
BULL_THRESHOLD = 65   # score >= BULL_THRESHOLD  → Bullish
BEAR_THRESHOLD = 35   # score <  BEAR_THRESHOLD  → Bearish
# else → Neutral

# ── Backtest defaults ─────────────────────────────────────────────────────────
DEFAULT_BACKTEST_YEARS = 2
ATR_STOP_MULTIPLIER = 2.0  # stop = 2 × ATR14

# ── Cache TTLs (seconds) ──────────────────────────────────────────────────────
CACHE_TTL_PRICE = 3600        # 1 hour
CACHE_TTL_COT   = 86400 * 7   # 1 week
CACHE_TTL_FRED  = 86400       # 1 day

# ── Alltick symbols ───────────────────────────────────────────────────────────
SYMBOL_XAUUSD = "XAUUSD"
SYMBOL_DXY    = "DXY"

# ── CFTC Gold futures COMEX code ──────────────────────────────────────────────
CFTC_GOLD_CODE = "088691"

# ── FRED series ───────────────────────────────────────────────────────────────
FRED_DFII10 = "DFII10"

# ── Watchlist alert defaults ──────────────────────────────────────────────────
ALERT_DFII10_LEVEL_DEFAULT = 2.0   # % — trigger if DFII10 crosses this
ALERT_COT_CHANGE_DEFAULT   = 10_000  # contracts/week
