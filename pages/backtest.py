"""
pages/backtest.py
Backtest analysis page:
  - Date range selector
  - Equity curve (Plotly)
  - Metrics card: Win Rate, Sharpe, Drawdown, Profit Factor
  - Trade log table
"""

from __future__ import annotations

import datetime
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config


def _equity_curve_chart(equity_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    if equity_df.empty:
        fig.update_layout(title="Equity Curve — no trades", height=320)
        return fig

    # Colour segments green/red
    pos_mask = equity_df["cumulative_pnl"] >= 0
    fig.add_trace(go.Scatter(
        x=equity_df["date"], y=equity_df["cumulative_pnl"],
        fill="tozeroy",
        fillcolor="rgba(34,197,94,0.12)",
        line=dict(color="#22c55e", width=2),
        name="Equity (PnL)",
    ))
    fig.add_hline(y=0, line_color="#6b7280", line_width=1)

    fig.update_layout(
        title="Equity Curve (Cumulative PnL, USD)",
        height=340,
        yaxis_title="Cumulative PnL (USD)",
        xaxis_title="Date",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e2e8f0",
        margin=dict(t=50, b=30, l=60, r=20),
    )
    return fig


def _monthly_returns_chart(trades_df: pd.DataFrame) -> go.Figure:
    if trades_df.empty:
        return go.Figure()

    t = trades_df.copy()
    t["exit_date"] = pd.to_datetime(t["exit_date"])
    t["month"] = t["exit_date"].dt.to_period("M").astype(str)
    monthly = t.groupby("month")["pnl_usd"].sum().reset_index()

    fig = go.Figure(go.Bar(
        x=monthly["month"], y=monthly["pnl_usd"],
        marker_color=["#22c55e" if v >= 0 else "#ef4444" for v in monthly["pnl_usd"]],
    ))
    fig.update_layout(
        title="Monthly PnL (USD)",
        height=260,
        xaxis_title="Month", yaxis_title="PnL (USD)",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e2e8f0",
        margin=dict(t=40, b=30, l=60, r=20),
    )
    return fig


def render(composite: dict):
    st.title("📈 Backtest Results")

    price_df = composite.get("price_df", pd.DataFrame())

    if price_df.empty:
        st.warning("No XAUUSD price data loaded. Configure your Alltick API key in Settings.")
        return

    # ── Date range selector ───────────────────────────────────────────────
    price_df["date"] = pd.to_datetime(price_df["date"])
    min_date = price_df["date"].min().date()
    max_date = price_df["date"].max().date()
    default_start = max_date - datetime.timedelta(days=365 * config.DEFAULT_BACKTEST_YEARS)

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=max(default_start, min_date),
                                   min_value=min_date, max_value=max_date)
    with col2:
        end_date = st.date_input("End Date", value=max_date,
                                 min_value=min_date, max_value=max_date)

    if st.button("▶ Run Backtest", type="primary"):
        _run_and_display(composite, str(start_date), str(end_date))
    elif "bt_trades" in st.session_state:
        _display_results(
            st.session_state["bt_trades"],
            st.session_state["bt_metrics"],
        )
    else:
        st.info("Select a date range and click **Run Backtest** to begin.")


def _run_and_display(composite: dict, start_date: str, end_date: str):
    from backtest.engine  import run_backtest
    from backtest.metrics import compute_metrics
    from signals.daily_signal import compute_rolling_score_history

    price_df  = composite.get("price_df",  pd.DataFrame())
    dfii10_df = composite.get("dfii10_df", pd.DataFrame())
    dxy_df    = composite.get("dxy_df",    pd.DataFrame())
    cot_df    = composite.get("cot_df",    pd.DataFrame())
    max_pain  = composite.get("max_pain",  None)

    with st.spinner("Computing scores and running backtest…"):
        # Build score history over full price range then filter for backtest
        score_hist = compute_rolling_score_history(
            price_df=price_df,
            dfii10_df=dfii10_df,
            dxy_df=dxy_df,
            cot_df=cot_df,
            max_pain=max_pain,
            lookback_days=len(price_df),
        )

        trades_df = run_backtest(price_df, score_hist, start_date=start_date, end_date=end_date)
        metrics   = compute_metrics(trades_df)

    st.session_state["bt_trades"]  = trades_df
    st.session_state["bt_metrics"] = metrics
    _display_results(trades_df, metrics)


def _display_results(trades_df: pd.DataFrame, metrics: dict):
    # ── Metrics cards ─────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Trades",   metrics["total_trades"])
    c2.metric("Win Rate",       f"{metrics['win_rate']:.1f}%")
    c3.metric("Profit Factor",  f"{metrics['profit_factor']:.2f}")
    c4.metric("Sharpe Ratio",   f"{metrics['sharpe']:.2f}")
    c5.metric("Max Drawdown",   f"{metrics['max_drawdown']:.1f}%")

    st.metric("Total PnL (USD)", f"${metrics['total_pnl']:,.2f}")

    st.divider()

    # ── Equity curve ──────────────────────────────────────────────────────
    st.plotly_chart(_equity_curve_chart(metrics["equity_curve"]), use_container_width=True)
    st.plotly_chart(_monthly_returns_chart(trades_df), use_container_width=True)

    # ── Trade log ─────────────────────────────────────────────────────────
    if not trades_df.empty:
        st.subheader("Trade Log")
        display = trades_df.copy()
        for col in ["entry_date", "exit_date"]:
            if col in display.columns:
                display[col] = pd.to_datetime(display[col]).dt.strftime("%Y-%m-%d")
        st.dataframe(display, use_container_width=True, hide_index=True)
    else:
        st.info("No trades generated for this date range.")
