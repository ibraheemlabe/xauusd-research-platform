"""
data/fetchers/cme_oi.py
Parses a user-provided CME Open Interest CSV export.
Extracts open interest by strike for puts and calls,
and computes the Max Pain level.

Max Pain = the strike at which total dollar loss to option holders
           (both puts and calls) is minimised.
"""

from __future__ import annotations

import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def parse_cme_oi(file_obj) -> tuple[pd.DataFrame, float | None]:
    """
    Parse a CME OI CSV file.

    Expected columns (case-insensitive, flexible):
        strike, call_oi, put_oi
    or the CME export format with columns like:
        Strike Price, Calls, Puts  (or similar)

    Returns
    -------
    (df, max_pain)
    df         : DataFrame with [strike, call_oi, put_oi]
    max_pain   : float or None
    """
    try:
        raw = pd.read_csv(file_obj)
    except Exception as exc:
        logger.error("Failed to read CME OI CSV: %s", exc)
        return pd.DataFrame(), None

    # Normalize column names
    raw.columns = [c.strip().lower().replace(" ", "_") for c in raw.columns]

    # Try to identify strike and OI columns flexibly
    strike_col = _find_col(raw, ["strike", "strike_price", "strike_px"])
    call_col   = _find_col(raw, ["call_oi", "calls", "call_open_interest", "call"])
    put_col    = _find_col(raw, ["put_oi", "puts", "put_open_interest", "put"])

    if not all([strike_col, call_col, put_col]):
        logger.warning(
            "Could not map CME OI columns. Found: %s", list(raw.columns)
        )
        return raw, None

    df = raw[[strike_col, call_col, put_col]].copy()
    df.rename(columns={strike_col: "strike", call_col: "call_oi", put_col: "put_oi"}, inplace=True)
    df["strike"]  = pd.to_numeric(df["strike"],  errors="coerce")
    df["call_oi"] = pd.to_numeric(df["call_oi"], errors="coerce").fillna(0)
    df["put_oi"]  = pd.to_numeric(df["put_oi"],  errors="coerce").fillna(0)
    df.dropna(subset=["strike"], inplace=True)
    df.sort_values("strike", inplace=True)
    df.reset_index(drop=True, inplace=True)

    max_pain = _compute_max_pain(df)
    return df, max_pain


def _compute_max_pain(df: pd.DataFrame) -> float | None:
    """
    Max Pain calculation:
    For each candidate strike S:
      - Call pain  = sum over all strikes K < S  of: call_oi[K] * (S - K)
      - Put  pain  = sum over all strikes K > S  of: put_oi[K]  * (K - S)
      - Total pain = call_pain + put_pain
    Max Pain = S that minimises total pain.
    """
    if df.empty:
        return None

    strikes = df["strike"].values
    call_oi = df["call_oi"].values
    put_oi  = df["put_oi"].values
    total_pain = np.zeros(len(strikes))

    for i, s in enumerate(strikes):
        # calls that are in-the-money at price S (K < S)
        call_pain = np.sum(call_oi[strikes < s] * (s - strikes[strikes < s]))
        # puts that are in-the-money at price S (K > S)
        put_pain  = np.sum(put_oi[strikes > s] * (strikes[strikes > s] - s))
        total_pain[i] = call_pain + put_pain

    return float(strikes[np.argmin(total_pain)])


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None
