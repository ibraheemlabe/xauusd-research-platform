"""
data/fetchers/fred.py
Fetches DFII10 (10-Year Treasury Inflation-Indexed Security, Constant Maturity)
from FRED via the fredapi library.
This series represents the 10-year real yield.
Cached to data/cache/dfii10.csv.
"""

from __future__ import annotations

import time
import logging
from pathlib import Path

import pandas as pd

import config

logger = logging.getLogger(__name__)

_CACHE_PATH: Path = config.CACHE_DIR / "dfii10.csv"


def _cache_fresh() -> bool:
    if not _CACHE_PATH.exists():
        return False
    return (time.time() - _CACHE_PATH.stat().st_mtime) < config.CACHE_TTL_FRED


def fetch_dfii10(force_refresh: bool = False) -> pd.DataFrame:
    """
    Return a DataFrame with columns [date, dfii10] (daily frequency).
    Dates are sorted ascending.

    Falls back to cache if FRED API key is missing or request fails.
    """
    if not force_refresh and _cache_fresh():
        logger.debug("Loading DFII10 from cache")
        return pd.read_csv(_CACHE_PATH, parse_dates=["date"])

    if not config.FRED_API_KEY:
        logger.warning("FRED_API_KEY not set — returning cached/empty DFII10")
        if _CACHE_PATH.exists():
            return pd.read_csv(_CACHE_PATH, parse_dates=["date"])
        return _empty_dfii10()

    try:
        from fredapi import Fred  # lazy import — optional dependency
        fred = Fred(api_key=config.FRED_API_KEY)
        series = fred.get_series(config.FRED_DFII10)
    except ImportError:
        logger.error("fredapi not installed. Run: pip install fredapi")
        return _load_cache_or_empty()
    except Exception as exc:
        logger.error("FRED request failed: %s", exc)
        return _load_cache_or_empty()

    df = series.reset_index()
    df.columns = ["date", "dfii10"]
    df["date"]   = pd.to_datetime(df["date"])
    df["dfii10"] = pd.to_numeric(df["dfii10"], errors="coerce")
    df.dropna(subset=["dfii10"], inplace=True)
    df.sort_values("date", inplace=True)
    df.reset_index(drop=True, inplace=True)

    df.to_csv(_CACHE_PATH, index=False)
    logger.info("Cached %d DFII10 rows", len(df))
    return df


def _load_cache_or_empty() -> pd.DataFrame:
    if _CACHE_PATH.exists():
        return pd.read_csv(_CACHE_PATH, parse_dates=["date"])
    return _empty_dfii10()


def _empty_dfii10() -> pd.DataFrame:
    return pd.DataFrame(columns=["date", "dfii10"])
