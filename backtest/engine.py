"""
backtest/engine.py
Vectorized backtest that aligns weekly macro scores with daily XAUUSD prices.

Logic:
  1. Forward-fill weekly macro scores to daily frequency.
  2. When the score crosses BULL_THRESHOLD or BEAR_THRESHOLD → new bias.
  3. Enter trade at next day's open in direction of bias.
  4. Exit on: opposite signal, end-of-week, or stop-loss (ATR_STOP_MULTIPLIER × ATR14).
  5. Output: trades_df with [entry_date, exit_date, direction, entry_px,
                              exit_px, pnl_usd, pnl_pct, bars_held, exit_reason]
"""

from __future__ import annotations

import logging
import numpy as np
import pandas as pd

import config

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helper: ATR-14
# ─────────────────────────────────────────────────────────────────────────────

def _compute_atr14(df: pd.DataFrame) -> pd.Series:
    high  = df["high"].values
    low   = df["low"].values
    close = df["close"].values

    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:]  - close[:-1]),
        ),
    )
    tr = np.concatenate([[np.nan], tr])
    atr = pd.Series(tr).rolling(14, min_periods=1).mean()
    return atr


# ─────────────────────────────────────────────────────────────────────────────
# Main backtest
# ─────────────────────────────────────────────────────────────────────────────

def run_backtest(
    price_df: pd.DataFrame,
    weekly_scores: pd.DataFrame,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    """
    Run vectorized backtest.

    Parameters
    ----------
    price_df      : XAUUSD daily OHLCV with columns [date, open, high, low, close]
    weekly_scores : DataFrame with columns [date, score]
    start_date    : ISO date string, inclusive (optional)
    end_date      : ISO date string, inclusive (optional)

    Returns
    -------
    trades_df : DataFrame of trades (one row per trade)
    """
    if price_df.empty:
        logger.warning("Price data is empty — cannot run backtest")
        return pd.DataFrame()

    # ── Prepare price ──────────────────────────────────────────────────────
    px = price_df.copy()
    px["date"] = pd.to_datetime(px["date"])
    px.sort_values("date", inplace=True)
    px.reset_index(drop=True, inplace=True)

    if start_date:
        px = px[px["date"] >= pd.Timestamp(start_date)]
    if end_date:
        px = px[px["date"] <= pd.Timestamp(end_date)]

    if px.empty:
        return pd.DataFrame()

    px.reset_index(drop=True, inplace=True)

    # ── ATR ───────────────────────────────────────────────────────────────
    px["atr14"] = _compute_atr14(px)

    # ── Forward-fill weekly scores to daily ───────────────────────────────
    if not weekly_scores.empty:
        ws = weekly_scores.copy()
        ws["date"] = pd.to_datetime(ws["date"])
        ws = ws.sort_values("date")
        # Reindex to daily dates, ffill
        px = px.merge(ws[["date", "score"]], on="date", how="left")
        px["score"] = px["score"].ffill().bfill().fillna(50.0)
    else:
        px["score"] = 50.0

    # ── Derive daily bias ─────────────────────────────────────────────────
    def _to_bias(s: float) -> int:
        if s >= config.BULL_THRESHOLD:
            return 1
        elif s < config.BEAR_THRESHOLD:
            return -1
        return 0

    px["bias"] = px["score"].apply(_to_bias)

    # ── Trade simulation ──────────────────────────────────────────────────
    trades = []
    in_trade   = False
    entry_px   = 0.0
    entry_date = None
    direction  = 0       # +1 long / -1 short
    stop_level = 0.0

    for i in range(len(px)):
        row  = px.iloc[i]
        bias = int(row["bias"])
        atr  = float(row["atr14"]) if not np.isnan(row["atr14"]) else 0.0

        # ── If in trade, check exits ──────────────────────────────────────
        if in_trade:
            exit_reason = None
            exit_px     = float(row["open"])  # conservative: exit at open

            # Stop-loss
            if direction == 1 and float(row["low"])  <= stop_level:
                exit_reason = "stop_loss"
                exit_px = stop_level
            elif direction == -1 and float(row["high"]) >= stop_level:
                exit_reason = "stop_loss"
                exit_px = stop_level

            # Signal flip
            if exit_reason is None and bias != direction and bias != 0:
                exit_reason = "signal_flip"

            # End of week
            if exit_reason is None and row["date"].weekday() == 4:  # Friday
                exit_reason = "end_of_week"

            if exit_reason:
                pnl_usd = (exit_px - entry_px) * direction
                pnl_pct = pnl_usd / entry_px * 100.0
                bars    = i - entry_idx  # type: ignore[name-defined]
                trades.append({
                    "entry_date":  entry_date,
                    "exit_date":   row["date"],
                    "direction":   "Long" if direction == 1 else "Short",
                    "entry_px":    round(entry_px, 2),
                    "exit_px":     round(exit_px, 2),
                    "pnl_usd":     round(pnl_usd, 2),
                    "pnl_pct":     round(pnl_pct, 4),
                    "bars_held":   bars,
                    "exit_reason": exit_reason,
                })
                in_trade = False
                continue

        # ── Entry logic ───────────────────────────────────────────────────
        if not in_trade and bias != 0:
            # Only enter if there is a clear directional bias
            in_trade   = True
            direction  = bias
            entry_px   = float(row["open"])
            entry_date = row["date"]
            entry_idx  = i  # noqa: F841
            stop_dist  = config.ATR_STOP_MULTIPLIER * atr
            if direction == 1:
                stop_level = entry_px - stop_dist
            else:
                stop_level = entry_px + stop_dist

    return pd.DataFrame(trades)
