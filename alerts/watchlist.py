"""
alerts/watchlist.py
Configurable threshold checks run on each dashboard refresh.
Fires Telegram alerts when conditions are met.
State is stored in Streamlit session_state to avoid re-firing on the same refresh.
"""

from __future__ import annotations

import logging
import pandas as pd

import config
from alerts.telegram_bot import alert_signal_flip, alert_dfii10_breach, alert_cot_change

logger = logging.getLogger(__name__)


def check_all(
    composite: dict,
    prev_label: str | None = None,
    dfii10_threshold: float = config.ALERT_DFII10_LEVEL_DEFAULT,
    cot_change_threshold: float = config.ALERT_COT_CHANGE_DEFAULT,
) -> list[str]:
    """
    Run all watchlist checks and fire Telegram alerts as needed.

    Parameters
    ----------
    composite           : dict returned by signals.composite.build_composite()
    prev_label          : previous signal label (to detect flips)
    dfii10_threshold    : DFII10 level that triggers an alert when crossed
    cot_change_threshold: absolute weekly COT net change that triggers an alert

    Returns
    -------
    list of alert messages that were fired
    """
    fired: list[str] = []
    score_dict = composite.get("score", {})
    current_label = score_dict.get("label", "Neutral")
    total_score = score_dict.get("total", 50.0)

    # ── Signal flip ───────────────────────────────────────────────────────
    if prev_label and current_label != prev_label:
        msg = f"Signal flip: {prev_label} → {current_label} (score {total_score:.1f})"
        logger.info(msg)
        alert_signal_flip(current_label, total_score)
        fired.append(msg)

    # ── DFII10 threshold ──────────────────────────────────────────────────
    dfii10_df: pd.DataFrame = composite.get("dfii10_df", pd.DataFrame())
    if not dfii10_df.empty and len(dfii10_df) >= 2:
        latest_val = float(dfii10_df["dfii10"].iloc[-1])
        prev_val   = float(dfii10_df["dfii10"].iloc[-2])

        crossed_above = prev_val < dfii10_threshold <= latest_val
        crossed_below = prev_val >= dfii10_threshold > latest_val

        if crossed_above:
            msg = f"DFII10 crossed above {dfii10_threshold:.2f}% (now {latest_val:.2f}%)"
            alert_dfii10_breach(latest_val, dfii10_threshold, "above")
            fired.append(msg)
        elif crossed_below:
            msg = f"DFII10 crossed below {dfii10_threshold:.2f}% (now {latest_val:.2f}%)"
            alert_dfii10_breach(latest_val, dfii10_threshold, "below")
            fired.append(msg)

    # ── COT net change ────────────────────────────────────────────────────
    cot_df: pd.DataFrame = composite.get("cot_df", pd.DataFrame())
    if not cot_df.empty and len(cot_df) >= 2:
        latest_net = float(cot_df["mm_net"].iloc[-1])
        prev_net   = float(cot_df["mm_net"].iloc[-2])
        change     = latest_net - prev_net

        if abs(change) >= cot_change_threshold:
            msg = f"COT net changed by {change:+,.0f} contracts (net now {latest_net:,.0f})"
            alert_cot_change(latest_net, change)
            fired.append(msg)

    return fired
