from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from financial_analyzer.market_data import fetch_ticker_bundle
from financial_analyzer.metrics import RATIO_LABELS, build_narrative, calculate_ratios, calculate_trends
from financial_analyzer.parsers import parse_uploaded_file


st.set_page_config(
    page_title="Financial Statement Analyzer",
    layout="wide",
)


def format_ratio(value: float | None, ratio_name: str) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    if ratio_name in {"gross_margin", "operating_margin", "net_margin", "roa", "roe", "equity_ratio"}:
        return f"{value:.1%}"
    return f"{value:.2f}x"


def metric_card(label: str, value: str, help_text: str) -> None:
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(145deg, #0f172a, #1e293b);
            padding: 1rem 1.1rem;
            border-radius: 18px;
            border: 1px solid rgba(148, 163, 184, 0.2);
            min-height: 132px;
        ">
            <div style="font-size: 0.9rem; color: #cbd5e1; margin-bottom: 0.7rem;">{label}</div>
            <div style="font-size: 2rem; font-weight: 700; color: #f8fafc;">{value}</div>
            <div style="font-size: 0.85rem; color: #94a3b8; margin-top: 0.7rem;">{help_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.markdown(
    """
    <style>
    .stApp {
        background:
            radial-gradient(circle at top left, rgba(14, 165, 233, 0.14), transparent 28%),
            radial-gradient(circle at top right, rgba(249, 115, 22, 0.14), transparent 30%),
            linear-gradient(180deg, #020617 0%, #0f172a 55%, #111827 100%);
    }
    h1, h2, h3 {
        letter-spacing: -0.02em;
    }
    [data-testid="stSidebar"] {
        background: rgba(15, 23, 42, 0.92);
        border-right: 1px solid rgba(148, 163, 184, 0.15);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Automated Financial Statement Analyzer")
st.caption("Analyze uploaded statements or public ticker data with ratio diagnostics, trend signals, and investor-style dashboards.")

with st.sidebar:
    st.header("Upload")
    data_source = st.radio("Data source", options=["Upload statements", "Yahoo Finance ticker"])
    uploaded_file = None
    ticker_symbol = ""
    if data_source == "Upload statements":
        uploaded_file = st.file_uploader("Financial statements", type=["csv", "xlsx", "xls", "pdf"])
    else:
        ticker_symbol = st.text_input("Ticker symbol", placeholder="AAPL")
    st.markdown(
        """
        **Supported inputs**

        For uploads, use:
        - `statement`
        - `line_item`
        - one column per year/period

        Or enter a public market ticker.
        """
    )
    if data_source == "Yahoo Finance ticker":
        st.caption("Ticker mode needs outbound internet access to Yahoo Finance endpoints.")
    show_raw = st.toggle("Show normalized dataset", value=False)


if data_source == "Upload statements" and not uploaded_file:
    st.info("Upload a statement file to begin. You can start with `sample_financials.csv` in this workspace.")
    st.markdown(
        """
        ### What this app analyzes
        - Profitability: margins, ROA, ROE
        - Liquidity: current ratio, quick ratio
        - Capital structure: debt-to-equity, equity ratio
        - Efficiency: asset turnover
        """
    )
    st.stop()

if data_source == "Yahoo Finance ticker" and not ticker_symbol.strip():
    st.info("Enter a ticker like `AAPL`, `MSFT`, or `NVDA` to pull financial statements and market context.")
    st.stop()


try:
    market_bundle = None
    if data_source == "Upload statements":
        financials_long = parse_uploaded_file(uploaded_file)
    else:
        market_bundle = fetch_ticker_bundle(ticker_symbol)
        financials_long = market_bundle.financials_long
    ratio_df = calculate_ratios(financials_long)
    trends_df = calculate_trends(financials_long)
    narrative = build_narrative(financials_long, ratio_df)
except Exception as exc:  # noqa: BLE001
    if data_source == "Upload statements":
        st.error(f"Could not analyze the uploaded file: {exc}")
    else:
        st.error(f"Could not analyze ticker data from Yahoo Finance: {exc}")
    st.stop()


periods = sorted(financials_long["period"].unique(), key=str)
latest_period = periods[-1]
latest_ratios = ratio_df[ratio_df["period"] == latest_period].set_index("ratio")

if market_bundle is not None:
    st.subheader(f"{market_bundle.summary.get('longName', market_bundle.summary.get('ticker'))} ({market_bundle.summary.get('ticker')})")
    meta_parts = [
        market_bundle.summary.get("sector"),
        market_bundle.summary.get("industry"),
        market_bundle.summary.get("currency"),
    ]
    st.caption(" | ".join(str(part) for part in meta_parts if part))

    market_columns = st.columns(4)
    market_cards = [
        ("Price", market_bundle.summary.get("currentPrice"), lambda v: f"${v:,.2f}" if isinstance(v, (int, float)) else "N/A"),
        ("Market Cap", market_bundle.summary.get("marketCap"), lambda v: f"${v/1_000_000_000:,.1f}B" if isinstance(v, (int, float)) else "N/A"),
        ("Trailing P/E", market_bundle.summary.get("trailingPE"), lambda v: f"{v:,.2f}x" if isinstance(v, (int, float)) else "N/A"),
        ("Analyst Mean Target", market_bundle.summary.get("targetMeanPrice"), lambda v: f"${v:,.2f}" if isinstance(v, (int, float)) else "N/A"),
    ]
    for column, (label, raw_value, formatter) in zip(market_columns, market_cards, strict=True):
        with column:
            metric_card(label, formatter(raw_value), "Yahoo Finance-derived investor context.")

st.subheader("Latest Period Snapshot")
card_columns = st.columns(4)
cards = [
    ("Return on Equity", "roe", "How efficiently shareholder capital generated earnings."),
    ("Return on Assets", "roa", "Net income produced for each dollar invested in assets."),
    ("Current Ratio", "current_ratio", "Short-term liquidity against current obligations."),
    ("Debt-to-Equity", "debt_to_equity", "Leverage relative to owners' equity."),
]
for column, (label, ratio_name, help_text) in zip(card_columns, cards, strict=True):
    with column:
        value = latest_ratios.loc[ratio_name, "value"] if ratio_name in latest_ratios.index else None
        metric_card(label, format_ratio(value, ratio_name), help_text)


if market_bundle is not None and not market_bundle.price_history.empty:
    st.subheader("Market Performance")
    history_df = market_bundle.price_history.copy()
    if "Date" in history_df.columns and "Close" in history_df.columns:
        price_chart = px.area(
            history_df,
            x="Date",
            y="Close",
            template="plotly_dark",
        )
        price_chart.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title="Date",
            yaxis_title="Close Price",
            height=340,
        )
        st.plotly_chart(price_chart, use_container_width=True)

chart_left, chart_right = st.columns((1.3, 1))

with chart_left:
    st.subheader("Ratio Dashboard")
    ratio_chart = px.line(
        ratio_df.dropna(subset=["value"]),
        x="period",
        y="value",
        color="label",
        markers=True,
        template="plotly_dark",
    )
    ratio_chart.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend_title_text="Ratio",
        yaxis_title="Value",
        xaxis_title="Period",
        height=430,
    )
    st.plotly_chart(ratio_chart, use_container_width=True)

with chart_right:
    st.subheader("Analyst Notes")
    for point in narrative:
        st.markdown(
            f"""
            <div style="
                background: rgba(15, 23, 42, 0.8);
                padding: 0.9rem 1rem;
                border-radius: 16px;
                border: 1px solid rgba(148, 163, 184, 0.15);
                margin-bottom: 0.75rem;
            ">
                <div style="font-weight: 700; color: #f8fafc; margin-bottom: 0.3rem;">{point.title}</div>
                <div style="color: #cbd5e1;">{point.detail}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


st.subheader("Statement Trends")
trend_left, trend_right = st.columns((1.2, 1))

with trend_left:
    key_line_items = financials_long[
        financials_long["line_item_normalized"].isin({"revenue", "net income", "total assets", "shareholders equity"})
    ].copy()
    if not key_line_items.empty:
        statement_chart = px.bar(
            key_line_items,
            x="period",
            y="value",
            color="line_item",
            barmode="group",
            template="plotly_dark",
        )
        statement_chart.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend_title_text="Line Item",
            yaxis_title="Amount",
            xaxis_title="Period",
            height=420,
        )
        st.plotly_chart(statement_chart, use_container_width=True)
    else:
        st.info("Not enough recognized line items were found for the trend chart.")

with trend_right:
    st.dataframe(
        trends_df.head(10).assign(
            percent_change=lambda frame: frame["percent_change"].map(
                lambda value: f"{value:.1%}" if pd.notna(value) else "N/A"
            ),
            start_value=lambda frame: frame["start_value"].map(lambda value: f"{value:,.0f}"),
            end_value=lambda frame: frame["end_value"].map(lambda value: f"{value:,.0f}"),
            absolute_change=lambda frame: frame["absolute_change"].map(lambda value: f"{value:,.0f}"),
        ),
        use_container_width=True,
        hide_index=True,
    )

if market_bundle is not None and market_bundle.news:
    st.subheader("Recent News")
    for item in market_bundle.news:
        title = item.get("title") or "Untitled article"
        publisher = item.get("publisher") or "Unknown publisher"
        link = item.get("link") or item.get("url")
        if link:
            st.markdown(f"- [{title}]({link}) ({publisher})")
        else:
            st.markdown(f"- {title} ({publisher})")


st.subheader("Ratio Table")
ratio_pivot = ratio_df.pivot_table(index="label", columns="period", values="value", aggfunc="first")
formatted_ratio_pivot = ratio_pivot.copy()
for ratio_name, label in RATIO_LABELS.items():
    if label not in formatted_ratio_pivot.index:
        continue
    formatted_ratio_pivot.loc[label] = formatted_ratio_pivot.loc[label].map(lambda value: format_ratio(value, ratio_name))

st.dataframe(formatted_ratio_pivot, use_container_width=True)

csv_output = ratio_df[["period", "label", "value"]].to_csv(index=False).encode("utf-8")
st.download_button(
    "Download ratio results",
    data=csv_output,
    file_name="financial_ratio_analysis.csv",
    mime="text/csv",
)

if show_raw:
    st.subheader("Normalized Input Data")
    st.dataframe(financials_long, use_container_width=True, hide_index=True)
