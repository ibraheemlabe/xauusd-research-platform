"""
pages/signals.py
Per-indicator deep-dive:
  - DFII10 vs XAUUSD time series + scatter
  - COT Managed Money net + price overlay
  - DXY correlation chart
  - CME OI strike distribution (call wall / put wall)
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import streamlit as st


# ─────────────────────────────────────────────────────────────────────────────

def _dfii10_chart(dfii10_df: pd.DataFrame, price_df: pd.DataFrame) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if not price_df.empty:
        fig.add_trace(go.Scatter(
            x=price_df["date"], y=price_df["close"],
            name="XAUUSD", line=dict(color="#fbbf24", width=1.5),
        ), secondary_y=False)

    if not dfii10_df.empty:
        fig.add_trace(go.Scatter(
            x=dfii10_df["date"], y=dfii10_df["dfii10"],
            name="DFII10 Real Yield", line=dict(color="#60a5fa", width=1.5, dash="dot"),
        ), secondary_y=True)
        fig.add_hline(y=0, line_color="#ef4444", line_dash="dash",
                      line_width=1, secondary_y=True)

    fig.update_layout(
        title="DFII10 Real Yield vs XAUUSD Price",
        height=360,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e2e8f0",
        legend=dict(orientation="h", y=1.05),
        margin=dict(t=50, b=30, l=60, r=60),
    )
    fig.update_yaxes(title_text="XAUUSD (USD/oz)", secondary_y=False)
    fig.update_yaxes(title_text="DFII10 (%)", secondary_y=True)
    return fig


def _dfii10_scatter(dfii10_df: pd.DataFrame, price_df: pd.DataFrame) -> go.Figure:
    if dfii10_df.empty or price_df.empty:
        return go.Figure(layout=go.Layout(title="No data for scatter"))

    merged = pd.merge_asof(
        price_df[["date", "close"]].sort_values("date"),
        dfii10_df[["date", "dfii10"]].sort_values("date"),
        on="date", direction="backward",
    ).dropna()

    fig = px.scatter(
        merged, x="dfii10", y="close",
        color="close",
        color_continuous_scale="YlOrRd",
        labels={"dfii10": "DFII10 Real Yield (%)", "close": "XAUUSD (USD/oz)"},
        title="DFII10 vs XAUUSD Scatter",
        trendline="ols",
    )
    fig.update_layout(
        height=320, paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", font_color="#e2e8f0",
        margin=dict(t=50, b=30, l=60, r=20),
    )
    return fig


def _cot_chart(cot_df: pd.DataFrame, price_df: pd.DataFrame) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if not price_df.empty:
        fig.add_trace(go.Scatter(
            x=price_df["date"], y=price_df["close"],
            name="XAUUSD", line=dict(color="#fbbf24", width=1.5),
        ), secondary_y=False)

    if not cot_df.empty:
        fig.add_trace(go.Bar(
            x=cot_df["date"], y=cot_df["mm_net"],
            name="MM Net", marker_color=[
                "#22c55e" if v >= 0 else "#ef4444" for v in cot_df["mm_net"]
            ],
            opacity=0.7,
        ), secondary_y=True)

    fig.update_layout(
        title="COT Managed Money Net Position + XAUUSD",
        height=360, paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", font_color="#e2e8f0",
        legend=dict(orientation="h", y=1.05),
        margin=dict(t=50, b=30, l=60, r=60),
    )
    fig.update_yaxes(title_text="XAUUSD (USD/oz)", secondary_y=False)
    fig.update_yaxes(title_text="MM Net (contracts)", secondary_y=True)
    return fig


def _dxy_correlation_chart(dxy_df: pd.DataFrame, price_df: pd.DataFrame) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if not price_df.empty:
        fig.add_trace(go.Scatter(
            x=price_df["date"], y=price_df["close"],
            name="XAUUSD", line=dict(color="#fbbf24", width=1.5),
        ), secondary_y=False)

    if not dxy_df.empty:
        fig.add_trace(go.Scatter(
            x=dxy_df["date"], y=dxy_df["close"],
            name="DXY", line=dict(color="#a78bfa", width=1.5),
        ), secondary_y=True)
        # 20-day SMA
        if len(dxy_df) >= 20:
            sma = dxy_df["close"].rolling(20).mean()
            fig.add_trace(go.Scatter(
                x=dxy_df["date"], y=sma,
                name="DXY SMA-20", line=dict(color="#a78bfa", dash="dot", width=1),
            ), secondary_y=True)

    fig.update_layout(
        title="DXY vs XAUUSD Correlation",
        height=360, paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", font_color="#e2e8f0",
        legend=dict(orientation="h", y=1.05),
        margin=dict(t=50, b=30, l=60, r=60),
    )
    fig.update_yaxes(title_text="XAUUSD (USD/oz)", secondary_y=False)
    fig.update_yaxes(title_text="DXY", secondary_y=True)
    return fig


def _oi_chart(oi_df: pd.DataFrame, max_pain: float | None, current_price: float | None) -> go.Figure:
    if oi_df.empty or "strike" not in oi_df.columns:
        fig = go.Figure()
        fig.update_layout(title="CME OI — Upload CSV in Settings", height=300,
                          paper_bgcolor="rgba(0,0,0,0)", font_color="#e2e8f0")
        return fig

    fig = go.Figure()
    if "call_oi" in oi_df.columns:
        fig.add_trace(go.Bar(
            x=oi_df["strike"], y=oi_df["call_oi"],
            name="Call OI", marker_color="rgba(34,197,94,0.7)",
        ))
    if "put_oi" in oi_df.columns:
        fig.add_trace(go.Bar(
            x=oi_df["strike"], y=oi_df["put_oi"],
            name="Put OI", marker_color="rgba(239,68,68,0.7)",
        ))

    if max_pain:
        fig.add_vline(x=max_pain, line_color="#f59e0b", line_dash="dash", line_width=2,
                      annotation_text=f"Max Pain ${max_pain:,.0f}", annotation_font_color="#f59e0b")
    if current_price:
        fig.add_vline(x=current_price, line_color="#fbbf24", line_width=2,
                      annotation_text=f"Spot ${current_price:,.0f}", annotation_font_color="#fbbf24")

    fig.update_layout(
        title="CME Gold OI — Call Wall / Put Wall",
        barmode="overlay", height=360,
        xaxis_title="Strike ($)", yaxis_title="Open Interest",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e2e8f0", margin=dict(t=50, b=30, l=60, r=20),
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────

def render(composite: dict):
    st.title("🔬 Signal Breakdown")

    dfii10_df = composite.get("dfii10_df", pd.DataFrame())
    price_df  = composite.get("price_df",  pd.DataFrame())
    dxy_df    = composite.get("dxy_df",    pd.DataFrame())
    cot_df    = composite.get("cot_df",    pd.DataFrame())
    oi_df     = composite.get("oi_df",     pd.DataFrame())
    max_pain  = composite.get("max_pain",  None)
    current_price = float(price_df["close"].iloc[-1]) if not price_df.empty else None

    tab1, tab2, tab3, tab4 = st.tabs(["DFII10", "COT Positioning", "DXY", "CME OI"])

    with tab1:
        st.plotly_chart(_dfii10_chart(dfii10_df, price_df), use_container_width=True)
        st.plotly_chart(_dfii10_scatter(dfii10_df, price_df), use_container_width=True)

    with tab2:
        st.plotly_chart(_cot_chart(cot_df, price_df), use_container_width=True)
        if not cot_df.empty:
            recent = cot_df.tail(12).copy()
            recent["date"] = recent["date"].dt.strftime("%Y-%m-%d")
            st.dataframe(recent[["date", "mm_long", "mm_short", "mm_net"]],
                         use_container_width=True, hide_index=True)

    with tab3:
        st.plotly_chart(_dxy_correlation_chart(dxy_df, price_df), use_container_width=True)
        if not dxy_df.empty and not price_df.empty:
            merged = pd.merge_asof(
                price_df[["date", "close"]].rename(columns={"close": "xauusd"}).sort_values("date"),
                dxy_df[["date", "close"]].rename(columns={"close": "dxy"}).sort_values("date"),
                on="date", direction="backward",
            ).dropna().tail(60)
            if len(merged) >= 5:
                corr = merged["xauusd"].corr(merged["dxy"])
                st.metric("60-day XAUUSD / DXY Correlation", f"{corr:.3f}",
                          help="Negative correlation is typical (strong USD → weaker gold)")

    with tab4:
        st.plotly_chart(_oi_chart(oi_df, max_pain, current_price), use_container_width=True)
        if max_pain:
            st.metric("Max Pain Level", f"${max_pain:,.0f}")
        if current_price and max_pain:
            dist_pct = (current_price - max_pain) / max_pain * 100
            st.metric(
                "Distance from Max Pain",
                f"{dist_pct:+.2f}%",
                help="Negative = below max pain (bullish signal)",
            )
