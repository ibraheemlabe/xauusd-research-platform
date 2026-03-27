"""
signals/daily_signal.py
Converts a weekly Composite Bull Score into a daily directional label.

Score >= BULL_THRESHOLD (65) → "Bullish"
Score in [BEAR_THRESHOLD, BULL_THRESHOLD) (35–64) → "Neutral"
Score < BEAR_THRESHOLD (35) → "Bearish"

When used with a historical score time-series, this module forward-fills
weekly scores to produce a daily signal series for backtesting.
"""

from __future__ import annotations

import pandas as pd
import config


def score_to_label(score: float) -> str:
    """Map a single score value to a directional label."""
    if score >= config.BULL_THRESHOLD:
        return "Bullish"
    elif score < config.BEAR_THRESHOLD:
        return "Bearish"
    else:
        return "Neutral"


def build_daily_signal(
    weekly_scores: pd.DataFrame,
    daily_dates: pd.DatetimeIndex,
) -> pd.DataFrame:
    """
    Build a daily signal frame from weekly scores.

    Parameters
    ----------
    weekly_scores : DataFrame with columns [date, score]
                    where date is the end-of-week date.
    daily_dates   : DatetimeIndex of trading days to fill.

    Returns
    -------
    DataFrame with columns [date, score, label]
    indexed on daily_dates (forward-filled from latest weekly score).
    """
    if weekly_scores.empty:
        df = pd.DataFrame({"date": daily_dates, "score": 50.0, "label": "Neutral"})
        return df

    ws = weekly_scores.copy()
    ws["date"] = pd.to_datetime(ws["date"])
    ws = ws.set_index("date").reindex(daily_dates, method="ffill")
    ws = ws.reset_index().rename(columns={"index": "date"})
    ws["score"] = ws["score"].fillna(50.0)
    ws["label"] = ws["score"].apply(score_to_label)
    return ws[["date", "score", "label"]]


def compute_rolling_score_history(
    price_df: pd.DataFrame,
    dfii10_df: pd.DataFrame,
    dxy_df: pd.DataFrame,
    cot_df: pd.DataFrame,
    max_pain: float | None,
    lookback_days: int = 90,
) -> pd.DataFrame:
    """
    Produce a rolling 30-day score history aligned to the price_df dates.
    For each day we take a snapshot of indicator values available up to that day.

    Returns DataFrame [date, score, label].
    """
    from signals.macro_score import compute_composite_score

    dates = price_df["date"].sort_values().iloc[-lookback_days:]
    rows = []

    for d in dates:
        dfii10_slice = None
        if not dfii10_df.empty:
            mask = dfii10_df["date"] <= d
            if mask.any():
                dfii10_slice = dfii10_df.loc[mask, "dfii10"].reset_index(drop=True)

        dxy_slice = None
        if not dxy_df.empty:
            mask = dxy_df["date"] <= d
            if mask.any():
                dxy_slice = dxy_df.loc[mask, "close"].reset_index(drop=True)

        cot_slice = None
        if not cot_df.empty:
            mask = cot_df["date"] <= d
            if mask.any():
                cot_slice = cot_df.loc[mask, "mm_net"].reset_index(drop=True)

        price_row = price_df[price_df["date"] <= d]
        current_price = float(price_row["close"].iloc[-1]) if not price_row.empty else None

        result = compute_composite_score(
            dfii10_series=dfii10_slice,
            dxy_close=dxy_slice,
            mm_net_series=cot_slice,
            current_price=current_price,
            max_pain=max_pain,
        )
        rows.append({"date": d, "score": result["total"], "label": result["label"]})

    return pd.DataFrame(rows)
