"""
data/fetchers/gram.py
Parses a user-provided WGC (World Gold Council) GRAM CSV export.
Extracts gold fair value and residual (over/under-valued vs model).

Expected CSV columns (flexible matching):
    date, fair_value, actual_price, residual (or similar)
"""

from __future__ import annotations

import logging
import pandas as pd

logger = logging.getLogger(__name__)


def parse_gram(file_obj) -> pd.DataFrame:
    """
    Parse a WGC GRAM CSV file.

    Returns
    -------
    DataFrame with columns: [date, fair_value, actual_price, residual]
    residual = actual_price - fair_value  (positive → over-valued)
    """
    try:
        raw = pd.read_csv(file_obj)
    except Exception as exc:
        logger.error("Failed to read GRAM CSV: %s", exc)
        return _empty_gram()

    raw.columns = [c.strip().lower().replace(" ", "_") for c in raw.columns]

    date_col       = _find_col(raw, ["date", "period", "as_of", "month"])
    fv_col         = _find_col(raw, ["fair_value", "model_value", "fair_price", "model_price"])
    actual_col     = _find_col(raw, ["actual_price", "price", "spot_price", "gold_price", "xauusd"])
    residual_col   = _find_col(raw, ["residual", "over_under", "deviation", "z_score"])

    if not date_col:
        logger.warning("No date column found in GRAM CSV. Columns: %s", list(raw.columns))
        return _empty_gram()

    df = raw.copy()

    # Build standardised frame
    out = pd.DataFrame()
    out["date"] = pd.to_datetime(df[date_col], infer_datetime_format=True, errors="coerce")

    if fv_col:
        out["fair_value"] = pd.to_numeric(df[fv_col], errors="coerce")
    else:
        out["fair_value"] = float("nan")

    if actual_col:
        out["actual_price"] = pd.to_numeric(df[actual_col], errors="coerce")
    else:
        out["actual_price"] = float("nan")

    if residual_col:
        out["residual"] = pd.to_numeric(df[residual_col], errors="coerce")
    elif fv_col and actual_col:
        out["residual"] = out["actual_price"] - out["fair_value"]
    else:
        out["residual"] = float("nan")

    out.dropna(subset=["date"], inplace=True)
    out.sort_values("date", inplace=True)
    out.reset_index(drop=True, inplace=True)
    return out


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _empty_gram() -> pd.DataFrame:
    return pd.DataFrame(columns=["date", "fair_value", "actual_price", "residual"])
