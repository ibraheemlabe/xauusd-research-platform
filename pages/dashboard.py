"""
pages/dashboard.py
Live macro dashboard:
  - Score gauge (ring chart) with Bullish / Neutral / Bearish label
  - Current readings table: DFII10, DXY trend, COT net, Max Pain
  - 30-day score history chart
  - Alert status badges per indicator
"""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go
import pandas as pd


def _label_color(label: str) -> str:
    return {"Bullish": "#22c55e", "Bearish": "#ef4444", "Neutral": "#f59e0b"}.get(label, "#6b7280")


def _gauge(score: float, label: str) -> go.Figure:
    color = _label_color(label)
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=score,
        delta={"reference": 50, "valueformat": ".1f"},
        number={"font": {"size": 48, "color": color}},
        title={"text": f"<b>{label}</b>", "font": {"size": 22, "color": color}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#334155"},
            "bar": {"color": color, "thickness": 0.25},
            "bgcolor": "rgba(0,0,0,0)",
            "borderwidth": 0,
            "steps": [
                {"range": [0,  35], "color": "rgba(239,68,68,0.15)"},
                {"range": [35, 65], "color": "rgba(245,158,11,0.12)"},
                {"range": [65, 100], "color": "rgba(34,197,94,0.15)"},
            ],
            "threshold": {
                "line": {"color": color, "width": 4},
                "thickness": 0.75,
                "value": score,
            },
        },
    ))
    fig.update_layout(
        height=280,
        margin=dict(t=30, b=10, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#e2e8f0",
    )
    return fig


def _score_history_chart(history_df: pd.DataFrame) -> go.Figure:
    if history_df.empty:
        fig = go.Figure()
        fig.update_layout(title="Score History (no data)", height=220)
        return fig

    colors = history_df["label"].map(
        {"Bullish": "#22c55e", "Bearish": "#ef4444", "Neutral": "#f59e0b"}
    ).fillna("#6b7280")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=history_df["date"], y=history_df["score"],
        mode="lines+markers",
        line=dict(color="#60a5fa", width=2),
        marker=dict(color=colors, size=6, line=dict(width=0)),
        name="Score",
    ))
    # Threshold bands
    fig.add_hrect(y0=65, y1=100, fillcolor="rgba(34,197,94,0.07)", line_width=0)
    fig.add_hrect(y0=0,  y1=35,  fillcolor="rgba(239,68,68,0.07)", line_width=0)
    fig.add_hline(y=65, line_dash="dot", line_color="#22c55e", line_width=1)
    fig.add_hline(y=35, line_dash="dot", line_color="#ef4444", line_width=1)

    fig.update_layout(
        title="30-Day Score History",
        yaxis=dict(range=[0, 100], title="Score"),
        xaxis_title="Date",
        height=260,
        margin=dict(t=40, b=30, l=50, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e2e8f0",
        showlegend=False,
    )
    return fig


def render(composite: dict, history_df: pd.DataFrame | None = None):
    """Render the Live Dashboard page."""
    st.title("📊 Live Macro Dashboard — XAUUSD")

    score_dict = composite.get("score", {})
    total      = score_dict.get("total",    50.0)
    label      = score_dict.get("label",    "Neutral")
    s_dfii10   = score_dict.get("dfii10",   0.0)
    s_dxy      = score_dict.get("dxy",      0.0)
    s_cot      = score_dict.get("cot",      0.0)
    s_mp       = score_dict.get("max_pain", 0.0)

    dfii10_df  = composite.get("dfii10_df",  pd.DataFrame())
    dxy_df     = composite.get("dxy_df",     pd.DataFrame())
    cot_df     = composite.get("cot_df",     pd.DataFrame())
    max_pain   = composite.get("max_pain",   None)
    price_df   = composite.get("price_df",   pd.DataFrame())

    errors = composite.get("errors", [])
    if errors:
        for e in errors:
            st.warning(f"⚠️ {e}")

    # ── Gauge ─────────────────────────────────────────────────────────────
    col_g, col_r = st.columns([1, 1.6])
    with col_g:
        st.plotly_chart(_gauge(total, label), use_container_width=True)

    # ── Current readings table ─────────────────────────────────────────────
    with col_r:
        st.subheader("Signal Readings")

        def _badge(score_val: float, max_w: float) -> str:
            pct = score_val / max_w if max_w else 0
            if pct >= 0.9:
                return "🟢"
            elif pct >= 0.45:
                return "🟡"
            return "🔴"

        # DFII10
        dfii10_val = (
            f"{dfii10_df['dfii10'].iloc[-1]:.2f}%" if not dfii10_df.empty else "N/A"
        )
        # DXY trend
        if not dxy_df.empty and len(dxy_df) >= 20:
            dxy_close = dxy_df["close"].iloc[-1]
            dxy_sma   = dxy_df["close"].iloc[-20:].mean()
            dxy_val   = f"{dxy_close:.2f} (SMA20: {dxy_sma:.2f})"
        else:
            dxy_val = "N/A"

        # COT
        cot_val = (
            f"{int(cot_df['mm_net'].iloc[-1]):,}" if not cot_df.empty else "N/A"
        )

        # Max Pain
        mp_val = f"${max_pain:,.0f}" if max_pain else "N/A"
        spot   = (
            f"${price_df['close'].iloc[-1]:,.2f}" if not price_df.empty else "N/A"
        )

        rows = [
            ("DFII10 Real Yield",    dfii10_val, s_dfii10, 30),
            ("DXY 20-day Trend",     dxy_val,    s_dxy,    25),
            ("COT MM Net",           cot_val,    s_cot,    25),
            ("CME Max Pain / Spot",  f"{mp_val} / {spot}", s_mp, 20),
        ]

        tbl = pd.DataFrame(rows, columns=["Indicator", "Value", "Score", "Max"])
        tbl["Status"] = tbl.apply(lambda r: _badge(r["Score"], r["Max"]), axis=1)
        tbl["Score"]  = tbl.apply(lambda r: f"{r['Score']:.0f}/{r['Max']}", axis=1)
        tbl.drop(columns=["Max"], inplace=True)
        st.dataframe(tbl, use_container_width=True, hide_index=True)

    st.divider()

    # ── 30-day score chart ────────────────────────────────────────────────
    if history_df is not None and not history_df.empty:
        st.plotly_chart(_score_history_chart(history_df), use_container_width=True)
    else:
        st.info("Score history will appear here after loading price + indicator data.")
