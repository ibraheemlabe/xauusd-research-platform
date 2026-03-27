"""
signals/composite.py
Orchestrates all data fetchers and the scoring function,
returning a single structured dict ready for display.
"""

from __future__ import annotations

import logging
import pandas as pd

logger = logging.getLogger(__name__)


def build_composite(
    force_refresh: bool = False,
    cme_oi_file=None,
    gram_file=None,
    cot_file=None,
) -> dict:
    """
    Fetch all signals, score them, and return a structured dict.

    Parameters
    ----------
    force_refresh  : bypass all caches
    cme_oi_file    : file-like object for CME OI CSV (optional)
    gram_file      : file-like object for WGC GRAM CSV (optional)
    cot_file       : file-like object for CFTC COT CSV (optional upload)

    Returns
    -------
    {
        'score':      dict,        # from compute_composite_score
        'price_df':   DataFrame,   # XAUUSD daily OHLCV
        'dxy_df':     DataFrame,   # DXY daily OHLCV
        'dfii10_df':  DataFrame,   # DFII10 daily
        'cot_df':     DataFrame,   # COT weekly
        'oi_df':      DataFrame,   # CME OI by strike (or empty)
        'max_pain':   float|None,
        'gram_df':    DataFrame,   # WGC GRAM (or empty)
        'errors':     list[str],
    }
    """
    from data.fetchers.alltick   import fetch_ohlcv
    from data.fetchers.fred      import fetch_dfii10
    from data.fetchers.cftc_cot  import fetch_cot, parse_cot_upload
    from data.fetchers.cme_oi    import parse_cme_oi
    from data.fetchers.gram      import parse_gram
    from signals.macro_score     import compute_composite_score
    import config

    errors: list[str] = []

    # ── Prices ──────────────────────────────────────────────────────────────
    try:
        price_df = fetch_ohlcv(config.SYMBOL_XAUUSD, "daily", force_refresh=force_refresh)
    except Exception as exc:
        logger.error("XAUUSD fetch failed: %s", exc)
        price_df = pd.DataFrame()
        errors.append(f"XAUUSD price fetch failed: {exc}")

    try:
        dxy_df = fetch_ohlcv(config.SYMBOL_DXY, "daily", force_refresh=force_refresh)
    except Exception as exc:
        logger.error("DXY fetch failed: %s", exc)
        dxy_df = pd.DataFrame()
        errors.append(f"DXY fetch failed: {exc}")

    # ── FRED DFII10 ──────────────────────────────────────────────────────────
    try:
        dfii10_df = fetch_dfii10(force_refresh=force_refresh)
    except Exception as exc:
        logger.error("DFII10 fetch failed: %s", exc)
        dfii10_df = pd.DataFrame()
        errors.append(f"DFII10 fetch failed: {exc}")

    # ── COT ──────────────────────────────────────────────────────────────────
    try:
        if cot_file is not None:
            cot_df = parse_cot_upload(cot_file)
        else:
            cot_df = fetch_cot(force_refresh=force_refresh)
    except Exception as exc:
        logger.error("COT fetch failed: %s", exc)
        cot_df = pd.DataFrame()
        errors.append(f"COT fetch failed: {exc}")

    # ── CME OI ───────────────────────────────────────────────────────────────
    oi_df, max_pain = pd.DataFrame(), None
    if cme_oi_file is not None:
        try:
            oi_df, max_pain = parse_cme_oi(cme_oi_file)
        except Exception as exc:
            logger.error("CME OI parse failed: %s", exc)
            errors.append(f"CME OI parse failed: {exc}")

    # ── GRAM ─────────────────────────────────────────────────────────────────
    gram_df = pd.DataFrame()
    if gram_file is not None:
        try:
            gram_df = parse_gram(gram_file)
        except Exception as exc:
            logger.error("GRAM parse failed: %s", exc)
            errors.append(f"GRAM parse failed: {exc}")

    # ── Assemble signal inputs ────────────────────────────────────────────────
    dfii10_series = dfii10_df["dfii10"] if not dfii10_df.empty else None
    dxy_close     = dxy_df["close"]     if not dxy_df.empty     else None
    mm_net_series = cot_df["mm_net"]    if not cot_df.empty      else None
    current_price = (
        float(price_df["close"].iloc[-1])
        if not price_df.empty else None
    )

    score = compute_composite_score(
        dfii10_series=dfii10_series,
        dxy_close=dxy_close,
        mm_net_series=mm_net_series,
        current_price=current_price,
        max_pain=max_pain,
    )

    return {
        "score":     score,
        "price_df":  price_df,
        "dxy_df":    dxy_df,
        "dfii10_df": dfii10_df,
        "cot_df":    cot_df,
        "oi_df":     oi_df,
        "max_pain":  max_pain,
        "gram_df":   gram_df,
        "errors":    errors,
    }
