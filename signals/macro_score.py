"""
signals/macro_score.py
Computes the weekly Composite Bull Score (0–100) from four macro signals.

Signal weights (from config.SIGNAL_WEIGHTS, sum = 100):
  - dfii10   : 30 pts  — bullish when real yield is falling or negative
  - dxy      : 25 pts  — bullish when 20-day trend is falling
  - cot      : 25 pts  — bullish when Managed Money net-long is rising
  - max_pain : 20 pts  — bullish when spot price is below CME max pain

Each component returns a normalised sub-score in [0, max_weight].
"""

from __future__ import annotations

import logging
import numpy as np
import pandas as pd

import config

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Individual signal scorers
# Each takes the relevant latest data and returns a float in [0, max_weight].
# ─────────────────────────────────────────────────────────────────────────────

def score_dfii10(dfii10_series: pd.Series, window: int = 20) -> float:
    """
    Real yield (DFII10) sub-score.
    Full score  : yield is negative  AND  falling over *window* days
    Partial (50%): yield is negative  OR   falling
    Zero        : yield is positive  AND  rising
    """
    w = config.SIGNAL_WEIGHTS["dfii10"]
    if dfii10_series is None or len(dfii10_series) < 2:
        return 0.0

    latest = float(dfii10_series.iloc[-1])
    prev   = float(dfii10_series.iloc[max(-window - 1, -len(dfii10_series))])

    is_negative = latest < 0.0
    is_falling  = latest < prev

    if is_negative and is_falling:
        return float(w)
    elif is_negative or is_falling:
        return float(w) * 0.5
    else:
        return 0.0


def score_dxy(dxy_close: pd.Series, window: int = 20) -> float:
    """
    DXY 20-day trend sub-score.
    Full score  : current close < 20-day SMA  (downtrend)
    Partial (50%): close < 20-day SMA by < 0.5%
    Zero        : close >= 20-day SMA
    """
    w = config.SIGNAL_WEIGHTS["dxy"]
    if dxy_close is None or len(dxy_close) < window:
        return 0.0

    sma   = float(dxy_close.iloc[-window:].mean())
    close = float(dxy_close.iloc[-1])
    diff_pct = (close - sma) / sma * 100  # negative → bearish DXY (good for gold)

    if diff_pct < -0.5:
        return float(w)
    elif diff_pct < 0:
        return float(w) * 0.5
    else:
        return 0.0


def score_cot(mm_net_series: pd.Series) -> float:
    """
    COT Managed Money net-long sub-score.
    Full score  : net position > 0 AND increased week-over-week
    Partial (50%): net > 0 but falling, or net < 0 but rising
    Zero        : net < 0 and falling
    """
    w = config.SIGNAL_WEIGHTS["cot"]
    if mm_net_series is None or len(mm_net_series) < 2:
        return 0.0

    latest = float(mm_net_series.iloc[-1])
    prev   = float(mm_net_series.iloc[-2])
    is_net_long = latest > 0
    is_rising   = latest > prev

    if is_net_long and is_rising:
        return float(w)
    elif is_net_long or is_rising:
        return float(w) * 0.5
    else:
        return 0.0


def score_max_pain(current_price: float | None, max_pain: float | None) -> float:
    """
    CME OI Max Pain sub-score.
    Full score  : price is below max pain (put wall support → bullish)
    Partial (50%): price within 1% above max pain
    Zero        : price clearly above max pain
    """
    w = config.SIGNAL_WEIGHTS["max_pain"]
    if current_price is None or max_pain is None or max_pain == 0:
        return 0.0

    diff_pct = (current_price - max_pain) / max_pain * 100

    if diff_pct < 0:
        return float(w)
    elif diff_pct <= 1.0:
        return float(w) * 0.5
    else:
        return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Composite scorer
# ─────────────────────────────────────────────────────────────────────────────

def compute_composite_score(
    dfii10_series: pd.Series | None = None,
    dxy_close: pd.Series | None = None,
    mm_net_series: pd.Series | None = None,
    current_price: float | None = None,
    max_pain: float | None = None,
) -> dict:
    """
    Compute the Composite Bull Score.

    Returns a dict:
    {
        'total': float,          # 0–100
        'dfii10': float,
        'dxy': float,
        'cot': float,
        'max_pain': float,
        'label': str,            # 'Bullish' | 'Neutral' | 'Bearish'
    }
    """
    s_dfii10    = score_dfii10(dfii10_series) if dfii10_series is not None else 0.0
    s_dxy       = score_dxy(dxy_close) if dxy_close is not None else 0.0
    s_cot       = score_cot(mm_net_series) if mm_net_series is not None else 0.0
    s_max_pain  = score_max_pain(current_price, max_pain)

    total = s_dfii10 + s_dxy + s_cot + s_max_pain
    total = float(np.clip(total, 0, 100))

    if total >= config.BULL_THRESHOLD:
        label = "Bullish"
    elif total < config.BEAR_THRESHOLD:
        label = "Bearish"
    else:
        label = "Neutral"

    return {
        "total":     total,
        "dfii10":    s_dfii10,
        "dxy":       s_dxy,
        "cot":       s_cot,
        "max_pain":  s_max_pain,
        "label":     label,
    }
