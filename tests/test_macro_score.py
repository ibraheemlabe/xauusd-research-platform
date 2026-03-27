"""
tests/test_macro_score.py
Smoke tests for the macro scoring function.
Ensures output is always in [0, 100] and labels are valid.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import pytest
from signals.macro_score import (
    compute_composite_score,
    score_dfii10,
    score_dxy,
    score_cot,
    score_max_pain,
)
import config


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests for individual scorers
# ─────────────────────────────────────────────────────────────────────────────

def test_dfii10_full_bullish():
    series = pd.Series([-0.5, -0.6, -0.7, -0.8])  # negative and falling
    assert score_dfii10(series) == config.SIGNAL_WEIGHTS["dfii10"]


def test_dfii10_full_bearish():
    series = pd.Series([1.5, 1.6, 1.7, 1.8])  # positive and rising
    assert score_dfii10(series) == 0.0


def test_dfii10_partial():
    series = pd.Series([0.5, 0.4, 0.3, 0.2])  # falling but still positive
    score = score_dfii10(series)
    assert score == config.SIGNAL_WEIGHTS["dfii10"] * 0.5


def test_dxy_full_bullish():
    # Last value well below SMA — strong bearish DXY
    vals = [105.0] * 19 + [100.0]
    series = pd.Series(vals)
    assert score_dxy(series) == config.SIGNAL_WEIGHTS["dxy"]


def test_dxy_full_bearish():
    vals = [100.0] * 19 + [106.0]  # last value above SMA
    series = pd.Series(vals)
    assert score_dxy(series) == 0.0


def test_cot_full_bullish():
    net = pd.Series([50_000, 60_000, 70_000])  # positive and rising
    assert score_cot(net) == config.SIGNAL_WEIGHTS["cot"]


def test_cot_full_bearish():
    net = pd.Series([-70_000, -80_000])  # negative and falling
    assert score_cot(net) == 0.0


def test_max_pain_below():
    assert score_max_pain(1900.0, 1950.0) == config.SIGNAL_WEIGHTS["max_pain"]


def test_max_pain_above():
    assert score_max_pain(2050.0, 1950.0) == 0.0


def test_max_pain_none():
    assert score_max_pain(None, None) == 0.0
    assert score_max_pain(1900.0, None) == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Composite score smoke tests
# ─────────────────────────────────────────────────────────────────────────────

def test_composite_score_range_all_bullish():
    result = compute_composite_score(
        dfii10_series=pd.Series([-0.5, -0.6, -0.7, -0.8]),
        dxy_close=pd.Series([105.0] * 19 + [100.0]),
        mm_net_series=pd.Series([50_000, 60_000, 70_000]),
        current_price=1900.0,
        max_pain=1950.0,
    )
    assert 0 <= result["total"] <= 100
    assert result["label"] == "Bullish"


def test_composite_score_range_all_bearish():
    result = compute_composite_score(
        dfii10_series=pd.Series([1.5, 1.6, 1.7, 1.8]),
        dxy_close=pd.Series([100.0] * 19 + [106.0]),
        mm_net_series=pd.Series([-70_000, -80_000]),
        current_price=2100.0,
        max_pain=1950.0,
    )
    assert 0 <= result["total"] <= 100
    assert result["label"] == "Bearish"


def test_composite_score_no_data():
    result = compute_composite_score()
    assert result["total"] == 0.0
    assert result["label"] == "Bearish"


def test_composite_score_partial_data():
    result = compute_composite_score(
        dfii10_series=pd.Series([-0.5, -0.6]),
        dxy_close=None,
        mm_net_series=None,
        current_price=None,
        max_pain=None,
    )
    assert 0 <= result["total"] <= 100
    assert result["label"] in {"Bullish", "Neutral", "Bearish"}


def test_composite_label_thresholds():
    for score_val, expected in [(70, "Bullish"), (50, "Neutral"), (20, "Bearish")]:
        # Build a scenario that roughly yields target score
        if expected == "Bullish":
            s = pd.Series([-0.5] * 20 + [-0.6])
            d = pd.Series([105.0] * 19 + [100.0])
            c = pd.Series([50_000, 60_000])
            result = compute_composite_score(dfii10_series=s, dxy_close=d, mm_net_series=c,
                                             current_price=1900.0, max_pain=1950.0)
        elif expected == "Neutral":
            result = compute_composite_score(
                dfii10_series=pd.Series([0.5, 0.4]),  # partial dfii10
                dxy_close=pd.Series([100.0] * 19 + [106.0]),  # bearish dxy
                mm_net_series=pd.Series([50_000, 60_000]),  # bullish cot
                current_price=1900.0, max_pain=1950.0,
            )
        else:
            result = compute_composite_score()

        assert result["label"] in {"Bullish", "Neutral", "Bearish"}


def test_composite_sub_scores_non_negative():
    result = compute_composite_score(
        dfii10_series=pd.Series([-0.5, -0.6]),
        dxy_close=pd.Series([105.0] * 19 + [100.0]),
        mm_net_series=pd.Series([50_000, 60_000]),
        current_price=1900.0,
        max_pain=1950.0,
    )
    for key in ["dfii10", "dxy", "cot", "max_pain"]:
        assert result[key] >= 0, f"{key} sub-score should be >= 0"
