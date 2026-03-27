"""
tests/test_backtest_engine.py
Verifies the backtest engine and that the equity curve sums correctly.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import numpy as np
import pytest
from backtest.engine  import run_backtest
from backtest.metrics import compute_metrics


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _make_price_df(n: int = 60, start_price: float = 1900.0) -> pd.DataFrame:
    """Generate synthetic daily OHLCV with a gentle uptrend."""
    dates = pd.date_range("2023-01-02", periods=n, freq="B")
    closes = start_price + np.cumsum(np.random.default_rng(42).normal(1, 5, n))
    df = pd.DataFrame({
        "date":   dates,
        "open":   closes - 1,
        "high":   closes + 3,
        "low":    closes - 3,
        "close":  closes,
        "volume": 10_000,
    })
    return df


def _make_weekly_scores(price_df: pd.DataFrame, score: float = 75.0) -> pd.DataFrame:
    """Weekly score series — all bullish by default."""
    weekly_dates = price_df["date"].iloc[::5]
    return pd.DataFrame({"date": weekly_dates, "score": score})


# ─────────────────────────────────────────────────────────────────────────────
# Engine tests
# ─────────────────────────────────────────────────────────────────────────────

def test_run_backtest_returns_dataframe():
    price_df = _make_price_df()
    scores   = _make_weekly_scores(price_df)
    trades   = run_backtest(price_df, scores)
    assert isinstance(trades, pd.DataFrame)


def test_run_backtest_expected_columns():
    price_df = _make_price_df()
    scores   = _make_weekly_scores(price_df)
    trades   = run_backtest(price_df, scores)
    if not trades.empty:
        for col in ["entry_date", "exit_date", "direction", "entry_px", "exit_px",
                    "pnl_usd", "pnl_pct", "bars_held", "exit_reason"]:
            assert col in trades.columns, f"Missing column: {col}"


def test_run_backtest_all_bearish_gives_shorts():
    price_df = _make_price_df()
    scores   = _make_weekly_scores(price_df, score=20.0)  # all bearish
    trades   = run_backtest(price_df, scores)
    if not trades.empty:
        assert (trades["direction"] == "Short").all(), "All bearish score should yield only Short trades"


def test_run_backtest_all_bullish_gives_longs():
    price_df = _make_price_df()
    scores   = _make_weekly_scores(price_df, score=80.0)
    trades   = run_backtest(price_df, scores)
    if not trades.empty:
        assert (trades["direction"] == "Long").all()


def test_run_backtest_neutral_score_no_trades():
    price_df = _make_price_df()
    scores   = _make_weekly_scores(price_df, score=50.0)  # all neutral
    trades   = run_backtest(price_df, scores)
    assert trades.empty or len(trades) == 0


def test_run_backtest_empty_price():
    trades = run_backtest(pd.DataFrame(), pd.DataFrame())
    assert trades.empty


def test_run_backtest_date_filter():
    price_df = _make_price_df(120)
    scores   = _make_weekly_scores(price_df, score=80.0)
    trades_full     = run_backtest(price_df, scores)
    trades_filtered = run_backtest(price_df, scores,
                                   start_date="2023-02-01", end_date="2023-03-31")
    # Filtered should have same or fewer trades
    assert len(trades_filtered) <= len(trades_full)


# ─────────────────────────────────────────────────────────────────────────────
# Metrics tests
# ─────────────────────────────────────────────────────────────────────────────

def test_metrics_equity_curve_sum():
    """Cumulative PnL final value must equal sum of individual trade PnLs."""
    price_df = _make_price_df()
    scores   = _make_weekly_scores(price_df, score=80.0)
    trades   = run_backtest(price_df, scores)

    if trades.empty:
        pytest.skip("No trades generated — skip equity curve test")

    metrics = compute_metrics(trades)
    eq = metrics["equity_curve"]

    assert not eq.empty
    expected_final = round(trades["pnl_usd"].sum(), 6)
    actual_final   = round(float(eq["cumulative_pnl"].iloc[-1]), 6)
    assert abs(expected_final - actual_final) < 0.01, (
        f"Equity curve final {actual_final} != trade PnL sum {expected_final}"
    )


def test_metrics_win_rate_range():
    price_df = _make_price_df()
    scores   = _make_weekly_scores(price_df, score=80.0)
    trades   = run_backtest(price_df, scores)

    if trades.empty:
        pytest.skip("No trades generated")

    metrics = compute_metrics(trades)
    assert 0.0 <= metrics["win_rate"] <= 100.0


def test_metrics_sharpe_is_numeric():
    price_df = _make_price_df()
    scores   = _make_weekly_scores(price_df, score=80.0)
    trades   = run_backtest(price_df, scores)

    if trades.empty:
        pytest.skip("No trades generated")

    metrics = compute_metrics(trades)
    assert isinstance(metrics["sharpe"], float)
    assert not (metrics["sharpe"] != metrics["sharpe"])  # not NaN


def test_metrics_empty_trades():
    metrics = compute_metrics(pd.DataFrame())
    assert metrics["total_trades"] == 0
    assert metrics["win_rate"]     == 0.0
    assert metrics["equity_curve"].empty


def test_metrics_max_drawdown_non_positive():
    price_df = _make_price_df()
    scores   = _make_weekly_scores(price_df, score=80.0)
    trades   = run_backtest(price_df, scores)

    if trades.empty:
        pytest.skip("No trades generated")

    metrics = compute_metrics(trades)
    assert metrics["max_drawdown"] <= 0.0, "Max drawdown should be <= 0%"
