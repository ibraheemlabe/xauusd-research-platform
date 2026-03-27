"""
backtest/metrics.py
Computes performance metrics from the trades_df produced by engine.run_backtest().

Metrics:
  - Win Rate
  - Profit Factor
  - Sharpe Ratio (annualised, assuming 252 trading days)
  - Max Drawdown (%)
  - Equity curve (cumulative PnL)
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_metrics(trades_df: pd.DataFrame) -> dict:
    """
    Parameters
    ----------
    trades_df : output of engine.run_backtest()

    Returns
    -------
    dict with keys:
      total_trades, win_rate, profit_factor, sharpe, max_drawdown,
      total_pnl, equity_curve (DataFrame [date, cumulative_pnl])
    """
    empty = {
        "total_trades":  0,
        "win_rate":      0.0,
        "profit_factor": 0.0,
        "sharpe":        0.0,
        "max_drawdown":  0.0,
        "total_pnl":     0.0,
        "equity_curve":  pd.DataFrame(columns=["date", "cumulative_pnl"]),
    }

    if trades_df is None or trades_df.empty:
        return empty

    pnl = trades_df["pnl_usd"].values.astype(float)
    dates = pd.to_datetime(trades_df["exit_date"])

    total = len(pnl)
    wins  = pnl[pnl > 0]
    losses = pnl[pnl <= 0]

    win_rate = len(wins) / total if total > 0 else 0.0

    gross_profit = wins.sum()  if len(wins)   > 0 else 0.0
    gross_loss   = abs(losses.sum()) if len(losses) > 0 else 1e-9
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Sharpe: use daily PnL returns; assume 1 trade per bar approximation
    if len(pnl) > 1:
        mean_pnl = np.mean(pnl)
        std_pnl  = np.std(pnl, ddof=1)
        # Annualise by sqrt(252 / avg_bars_held)
        avg_bars = trades_df["bars_held"].mean() if "bars_held" in trades_df.columns else 5
        avg_bars = max(avg_bars, 1)
        ann_factor = np.sqrt(252 / avg_bars)
        sharpe = (mean_pnl / std_pnl) * ann_factor if std_pnl > 0 else 0.0
    else:
        sharpe = 0.0

    # Equity curve
    equity = pd.DataFrame({"date": dates, "pnl": pnl})
    equity.sort_values("date", inplace=True)
    equity["cumulative_pnl"] = equity["pnl"].cumsum()

    # Max Drawdown on cumulative PnL
    cumulative = equity["cumulative_pnl"].values
    rolling_max = np.maximum.accumulate(cumulative)
    drawdowns   = cumulative - rolling_max
    max_dd      = float(drawdowns.min()) if len(drawdowns) > 0 else 0.0
    # Express as % of rolling max (avoid divide-by-zero)
    nonzero_max = rolling_max.copy()
    nonzero_max[nonzero_max == 0] = 1
    dd_pct = (drawdowns / nonzero_max) * 100
    max_dd_pct = float(dd_pct.min())

    return {
        "total_trades":  total,
        "win_rate":      round(win_rate * 100, 2),
        "profit_factor": round(profit_factor, 3),
        "sharpe":        round(sharpe, 3),
        "max_drawdown":  round(max_dd_pct, 2),
        "total_pnl":     round(float(pnl.sum()), 2),
        "equity_curve":  equity[["date", "cumulative_pnl"]].reset_index(drop=True),
    }
