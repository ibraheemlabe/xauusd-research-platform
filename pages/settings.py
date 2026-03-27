"""
pages/settings.py
Settings & Data Upload:
  - API key status
  - CSV upload widgets (CME OI, WGC GRAM, CFTC COT)
  - Alert threshold configuration
  - Send test Telegram message
  - Cache clear button
"""

from __future__ import annotations

import shutil
import streamlit as st
import config


def render():
    st.title("⚙️ Settings & Data Upload")

    # ── API Key Status ────────────────────────────────────────────────────
    st.subheader("API Key Status")

    def _status(key: str, name: str):
        ok = bool(key)
        icon = "✅" if ok else "❌"
        st.markdown(f"{icon} **{name}** — {'configured' if ok else 'not set (add to .env)'}")

    _status(config.ALLTICK_API_KEY,    "Alltick API Key")
    _status(config.FRED_API_KEY,       "FRED API Key")
    _status(config.TELEGRAM_BOT_TOKEN, "Telegram Bot Token")
    _status(config.TELEGRAM_CHAT_ID,   "Telegram Chat ID")
    st.caption("Edit the `.env` file in the project root to add keys.")

    st.divider()

    # ── Data Upload ───────────────────────────────────────────────────────
    st.subheader("CSV Data Upload")
    st.caption(
        "Upload optional CSV exports here. Uploaded files are stored in session state "
        "and used for the current session only."
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**CME OI Export**")
        st.caption("Columns: strike, call_oi, put_oi (or similar)")
        cme_file = st.file_uploader("CME OI CSV", type=["csv"], key="cme_upload")
        if cme_file:
            st.session_state["cme_oi_file"] = cme_file
            st.success("CME OI file loaded ✓")

    with col2:
        st.markdown("**WGC GRAM Export**")
        st.caption("Columns: date, fair_value, actual_price, residual (flexible)")
        gram_file = st.file_uploader("GRAM CSV", type=["csv"], key="gram_upload")
        if gram_file:
            st.session_state["gram_file"] = gram_file
            st.success("GRAM file loaded ✓")

    with col3:
        st.markdown("**CFTC COT Export**")
        st.caption("Full CFTC disaggregated CSV — auto-filtered for Gold (088691)")
        cot_file = st.file_uploader("COT CSV", type=["csv"], key="cot_upload")
        if cot_file:
            st.session_state["cot_file"] = cot_file
            st.success("COT file loaded ✓")

    st.divider()

    # ── Alert Thresholds ──────────────────────────────────────────────────
    st.subheader("Alert Thresholds")

    col_a, col_b = st.columns(2)
    with col_a:
        dfii10_thresh = st.number_input(
            "DFII10 alert level (%)",
            value=float(st.session_state.get("dfii10_thresh", config.ALERT_DFII10_LEVEL_DEFAULT)),
            step=0.1, format="%.2f",
            help="Alert fires when DFII10 crosses this level (up or down)",
        )
        st.session_state["dfii10_thresh"] = dfii10_thresh

    with col_b:
        cot_thresh = st.number_input(
            "COT net change alert (contracts)",
            value=float(st.session_state.get("cot_thresh", config.ALERT_COT_CHANGE_DEFAULT)),
            step=1000.0, format="%.0f",
            help="Alert fires when weekly COT net change exceeds this absolute value",
        )
        st.session_state["cot_thresh"] = cot_thresh

    st.divider()

    # ── Telegram test ─────────────────────────────────────────────────────
    st.subheader("Telegram Alerts")
    if st.button("📨 Send Test Telegram Message"):
        from alerts.telegram_bot import send_test_message
        with st.spinner("Sending…"):
            ok = send_test_message()
        if ok:
            st.success("Test message sent! Check your Telegram.")
        else:
            st.error("Failed to send. Check BOT_TOKEN and CHAT_ID in .env")

    st.divider()

    # ── Cache management ──────────────────────────────────────────────────
    st.subheader("Cache Management")
    cache_files = list(config.CACHE_DIR.glob("*.csv"))
    if cache_files:
        st.caption(f"{len(cache_files)} cached file(s) in `data/cache/`:")
        for f in cache_files:
            size_kb = f.stat().st_size / 1024
            st.markdown(f"- `{f.name}` ({size_kb:.1f} KB)")
    else:
        st.caption("Cache is empty.")

    if st.button("🗑️ Clear All Cache"):
        for f in config.CACHE_DIR.glob("*.csv"):
            f.unlink(missing_ok=True)
        st.success("Cache cleared. Data will be re-fetched on next refresh.")
        st.rerun()
