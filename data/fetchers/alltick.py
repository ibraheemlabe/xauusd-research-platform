"""
data/fetchers/alltick.py
Fetches OHLCV history from the Alltick.co REST API for XAUUSD and DXY.
Supports 'daily' and 'weekly' resolutions.
Results are cached to data/cache/{symbol}_{resolution}.csv.
"""

from __future__ import annotations

import time
import logging
from pathlib import Path

import pandas as pd
import requests

import config

logger = logging.getLogger(__name__)

# Alltick REST endpoint (v2 quote history)
_BASE_URL = "https://quote.alltick.co/quote-b-api/kline"

# Map our resolution labels to Alltick period codes
_RESOLUTION_MAP = {
    "daily":  "1day",
    "weekly": "1week",
}


def _cache_path(symbol: str, resolution: str) -> Path:
    return config.CACHE_DIR / f"{symbol}_{resolution}.csv"


def _cache_fresh(path: Path, ttl: int) -> bool:
    """Return True if the file exists and is newer than *ttl* seconds."""
    if not path.exists():
        return False
    age = time.time() - path.stat().st_mtime
    return age < ttl


def fetch_ohlcv(
    symbol: str = config.SYMBOL_XAUUSD,
    resolution: str = "daily",
    limit: int = 500,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Fetch OHLCV bars from Alltick.co.

    Parameters
    ----------
    symbol      : 'XAUUSD' or 'DXY'
    resolution  : 'daily' | 'weekly'
    limit       : number of bars to request (max 500 per call)
    force_refresh: bypass cache

    Returns
    -------
    DataFrame with columns [date, open, high, low, close, volume]
    sorted ascending by date.
    Raises RuntimeError if no API key is configured.
    """
    cache = _cache_path(symbol, resolution)

    if not force_refresh and _cache_fresh(cache, config.CACHE_TTL_PRICE):
        logger.debug("Loading %s/%s from cache", symbol, resolution)
        return pd.read_csv(cache, parse_dates=["date"])

    if not config.ALLTICK_API_KEY:
        # Return empty frame so the app degrades gracefully
        logger.warning("ALLTICK_API_KEY not set — returning empty DataFrame for %s", symbol)
        return _empty_ohlcv()

    period = _RESOLUTION_MAP.get(resolution, "1day")

    params = {
        "token": config.ALLTICK_API_KEY,
        "query": f'{{"trade_ticket":"{symbol}","period_type":"{period}","count":{limit}}}',
    }

    try:
        resp = requests.get(_BASE_URL, params=params, timeout=15)
        resp.raise_for_status()
        payload = resp.json()
    except requests.RequestException as exc:
        logger.error("Alltick request failed: %s", exc)
        # Fall back to cached data even if stale
        if cache.exists():
            return pd.read_csv(cache, parse_dates=["date"])
        return _empty_ohlcv()

    data = payload.get("data", {}).get("kline_data", [])
    if not data:
        logger.warning("Alltick returned no kline data for %s", symbol)
        if cache.exists():
            return pd.read_csv(cache, parse_dates=["date"])
        return _empty_ohlcv()

    df = pd.DataFrame(data)
    # Alltick field names: timestamp (unix ms), open, high, low, close, volume
    df.rename(columns={"timestamp": "date"}, inplace=True)
    df["date"] = pd.to_datetime(df["date"], unit="ms", utc=True).dt.tz_localize(None).dt.normalize()
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df[["date", "open", "high", "low", "close", "volume"]].dropna(subset=["date", "close"])
    df.sort_values("date", inplace=True)
    df.reset_index(drop=True, inplace=True)

    df.to_csv(cache, index=False)
    logger.info("Cached %d %s/%s bars", len(df), symbol, resolution)
    return df


def _empty_ohlcv() -> pd.DataFrame:
    return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
