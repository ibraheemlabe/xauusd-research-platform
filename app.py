"""
app.py — XAUUSD Macro Research Platform
Entry point for the Streamlit application.

Run with:
    streamlit run app.py

Navigation (sidebar):
    📊 Live Dashboard
    🔬 Signal Breakdown
    📈 Backtest Results
    ⚙️ Settings / Data Upload
"""

import logging
import streamlit as st

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="XAUUSD Research Platform",
    page_icon="🥇",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Dark card feel */
    [data-testid="stMetric"] {
        background: rgba(255,255,255,0.04);
        border-radius: 10px;
        padding: 12px 16px;
    }
    [data-testid="stMetricLabel"] { font-size: 0.8rem; color: #94a3b8; }
    [data-testid="stMetricValue"] { font-size: 1.4rem; }
    /* Sidebar nav */
    .nav-item { padding: 8px 12px; border-radius: 6px; cursor: pointer; }
    .nav-item:hover { background: rgba(255,255,255,0.06); }
</style>
""", unsafe_allow_html=True)

# ── Sidebar navigation ────────────────────────────────────────────────────────
PAGES = {
    "📊 Live Dashboard":     "dashboard",
    "🔬 Signal Breakdown":   "signals",
    "📈 Backtest Results":   "backtest",
    "⚙️ Settings & Upload": "settings",
}

with st.sidebar:
    st.markdown("## 🥇 XAUUSD Research")
    st.divider()
    page_name = st.radio("Navigation", list(PAGES.keys()), label_visibility="collapsed")
    st.divider()

    # ── Refresh controls ─────────────────────────────────────────────────
    st.markdown("**Data Refresh**")
    force_refresh = st.button("🔄 Refresh All Data", use_container_width=True)

    # Composite data is cached in session_state to avoid re-fetching on every
    # widget interaction.  Clicking "Refresh" forces re-fetch.
    if force_refresh or "composite" not in st.session_state:
        from signals.composite import build_composite
        with st.spinner("Fetching data…"):
            st.session_state["composite"] = build_composite(
                force_refresh=True,
                cme_oi_file=st.session_state.get("cme_oi_file"),
                gram_file=st.session_state.get("gram_file"),
                cot_file=st.session_state.get("cot_file"),
            )
        # Clear previous watchlist state so alerts can re-fire
        st.session_state.pop("prev_label", None)

    composite = st.session_state["composite"]
    score = composite.get("score", {})
    label = score.get("label", "Neutral")
    total = score.get("total", 50.0)

    # ── Score summary in sidebar ─────────────────────────────────────────
    colour = {"Bullish": "green", "Bearish": "red", "Neutral": "orange"}.get(label, "gray")
    st.markdown(
        f"**Score:** :{colour}[{total:.1f}/100 — **{label}**]"
    )

    # ── Watchlist check ──────────────────────────────────────────────────
    from alerts.watchlist import check_all
    fired = check_all(
        composite,
        prev_label=st.session_state.get("prev_label"),
        dfii10_threshold=st.session_state.get("dfii10_thresh", 2.0),
        cot_change_threshold=st.session_state.get("cot_thresh", 10_000),
    )
    st.session_state["prev_label"] = label
    if fired:
        for msg in fired:
            st.sidebar.warning(f"🔔 {msg}")

    st.caption("Data refreshes automatically on file upload or manual refresh.")

# ── Route to page ─────────────────────────────────────────────────────────────
page_key = PAGES[page_name]

if page_key == "dashboard":
    from pages.dashboard import render
    from signals.daily_signal import compute_rolling_score_history

    price_df  = composite.get("price_df", None)
    dfii10_df = composite.get("dfii10_df", None)
    dxy_df    = composite.get("dxy_df", None)
    cot_df    = composite.get("cot_df", None)
    max_pain  = composite.get("max_pain", None)

    history_df = None
    if price_df is not None and not price_df.empty:
        import pandas as pd
        history_df = compute_rolling_score_history(
            price_df=price_df,
            dfii10_df=dfii10_df if dfii10_df is not None else pd.DataFrame(),
            dxy_df=dxy_df if dxy_df is not None else pd.DataFrame(),
            cot_df=cot_df if cot_df is not None else pd.DataFrame(),
            max_pain=max_pain,
            lookback_days=30,
        )
    render(composite, history_df=history_df)

elif page_key == "signals":
    from pages.signals import render
    render(composite)

elif page_key == "backtest":
    from pages.backtest import render
    render(composite)

elif page_key == "settings":
    from pages.settings import render
    render()
    # After settings changes, re-build composite if uploads changed
    new_composite_needed = any(
        st.session_state.get(k) for k in ["cme_oi_file", "gram_file", "cot_file"]
        if st.session_state.get(k) and st.session_state.get(k) not in (
            composite.get("oi_df"), composite.get("gram_df"), composite.get("cot_df")
        )
    )
