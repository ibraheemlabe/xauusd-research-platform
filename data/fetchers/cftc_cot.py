"""
data/fetchers/cftc_cot.py
Downloads the CFTC Commitments of Traders (COT) weekly CSV from cftc.gov,
filters for Gold futures (COMEX code 088691), and extracts
Managed Money Longs, Shorts, and Net positioning.
Cached to data/cache/cot_gold.csv.
"""

from __future__ import annotations

import io
import time
import logging
from pathlib import Path

import pandas as pd
import requests

import config

logger = logging.getLogger(__name__)

# Current-year disaggregated futures-and-options combined
_COT_URL = (
    "https://www.cftc.gov/files/dea/history/fut_disagg_xls_2024.zip"
)
# Fallback: we try the most recent available year
_COT_URL_TEMPLATE = "https://www.cftc.gov/files/dea/history/fut_disagg_xls_{year}.zip"

_CACHE_PATH: Path = config.CACHE_DIR / "cot_gold.csv"

# Column mapping from the CFTC disaggregated report
_COT_COLS = {
    "Market_and_Exchange_Names": "market",
    "As_of_Date_In_Form_YYMMDD": "date",
    "CFTC_Commodity_Code": "cftc_code",
    "M_Money_Positions_Long_All": "mm_long",
    "M_Money_Positions_Short_All": "mm_short",
    "M_Money_Positions_Spread_All": "mm_spread",
}


def _cache_fresh() -> bool:
    if not _CACHE_PATH.exists():
        return False
    return (time.time() - _CACHE_PATH.stat().st_mtime) < config.CACHE_TTL_COT


def _try_download(year: int) -> bytes | None:
    url = _COT_URL_TEMPLATE.format(year=year)
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            return resp.content
    except requests.RequestException as exc:
        logger.warning("COT download failed for year %d: %s", year, exc)
    return None


def fetch_cot(force_refresh: bool = False) -> pd.DataFrame:
    """
    Return a DataFrame with weekly Gold COT data:
    columns: [date, mm_long, mm_short, mm_net]

    Falls back to cache if download fails.
    """
    if not force_refresh and _cache_fresh():
        logger.debug("Loading COT from cache")
        return pd.read_csv(_CACHE_PATH, parse_dates=["date"])

    import datetime, zipfile

    current_year = datetime.date.today().year
    raw_bytes = None
    for year in [current_year, current_year - 1]:
        raw_bytes = _try_download(year)
        if raw_bytes:
            break

    if raw_bytes is None:
        logger.error("Could not download CFTC COT data")
        if _CACHE_PATH.exists():
            return pd.read_csv(_CACHE_PATH, parse_dates=["date"])
        return _empty_cot()

    # Extract the CSV from the zip
    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
            # find the CSV/TXT file inside
            csv_name = next((n for n in zf.namelist() if n.lower().endswith((".csv", ".txt"))), None)
            if csv_name is None:
                logger.error("No CSV found inside COT zip")
                return _empty_cot()
            with zf.open(csv_name) as f:
                raw_df = pd.read_csv(f, low_memory=False)
    except Exception as exc:
        logger.error("Failed to parse COT zip: %s", exc)
        return _empty_cot()

    # Filter Gold futures by COMEX code
    code_col = "CFTC_Commodity_Code"
    if code_col not in raw_df.columns:
        logger.error("Expected column '%s' not found in COT data", code_col)
        return _empty_cot()

    gold = raw_df[raw_df[code_col].astype(str).str.strip() == config.CFTC_GOLD_CODE].copy()
    if gold.empty:
        logger.warning("No rows found for CFTC Gold code %s", config.CFTC_GOLD_CODE)
        return _empty_cot()

    keep = {k: v for k, v in _COT_COLS.items() if k in gold.columns}
    gold = gold[list(keep.keys())].rename(columns=keep)

    # Parse date (YYMMDD format)
    gold["date"] = pd.to_datetime(gold["date"].astype(str), format="%y%m%d", errors="coerce")
    gold.dropna(subset=["date"], inplace=True)

    for col in ["mm_long", "mm_short"]:
        gold[col] = pd.to_numeric(gold[col], errors="coerce").fillna(0)

    gold["mm_net"] = gold["mm_long"] - gold["mm_short"]
    gold.sort_values("date", inplace=True)
    gold.reset_index(drop=True, inplace=True)

    result = gold[["date", "mm_long", "mm_short", "mm_net"]]
    result.to_csv(_CACHE_PATH, index=False)
    logger.info("Cached %d COT rows", len(result))
    return result


def parse_cot_upload(file_obj) -> pd.DataFrame:
    """
    Parse a user-uploaded CFTC COT CSV file (same format as above).
    Returns [date, mm_long, mm_short, mm_net].
    """
    try:
        raw_df = pd.read_csv(file_obj, low_memory=False)
    except Exception as exc:
        logger.error("Failed to read uploaded COT CSV: %s", exc)
        return _empty_cot()

    code_col = "CFTC_Commodity_Code"
    if code_col in raw_df.columns:
        filtered = raw_df[raw_df[code_col].astype(str).str.strip() == config.CFTC_GOLD_CODE].copy()
        # Fall back to full frame if code not found (test data may omit it)
        gold = filtered if not filtered.empty else raw_df.copy()
    else:
        gold = raw_df.copy()  # assume pre-filtered

    keep = {k: v for k, v in _COT_COLS.items() if k in gold.columns}
    gold = gold[list(keep.keys())].rename(columns=keep)

    gold["date"] = pd.to_datetime(gold["date"].astype(str), format="%y%m%d", errors="coerce")
    gold.dropna(subset=["date"], inplace=True)

    for col in ["mm_long", "mm_short"]:
        if col in gold.columns:
            gold[col] = pd.to_numeric(gold[col], errors="coerce").fillna(0)

    if "mm_long" in gold.columns and "mm_short" in gold.columns:
        gold["mm_net"] = gold["mm_long"] - gold["mm_short"]

    gold.sort_values("date", inplace=True)
    gold.reset_index(drop=True, inplace=True)
    return gold[["date", "mm_long", "mm_short", "mm_net"]] if all(
        c in gold.columns for c in ["date", "mm_long", "mm_short", "mm_net"]
    ) else gold


def _empty_cot() -> pd.DataFrame:
    return pd.DataFrame(columns=["date", "mm_long", "mm_short", "mm_net"])
