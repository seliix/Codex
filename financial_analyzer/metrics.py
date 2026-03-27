from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable

import pandas as pd


ALIASES: dict[str, set[str]] = {
    "revenue": {"revenue", "sales", "net sales", "total revenue", "total sales"},
    "cost_of_revenue": {
        "cost of revenue",
        "cost of sales",
        "cogs",
        "cost of goods sold",
        "cost of revenue",
        "cost of goods sold",
    },
    "gross_profit": {"gross profit"},
    "operating_income": {"operating income", "ebit", "income from operations", "operatingincome"},
    "net_income": {"net income", "net earnings", "profit after tax", "netincome"},
    "current_assets": {"current assets", "total current assets", "currentassets"},
    "current_liabilities": {"current liabilities", "total current liabilities", "currentliabilities"},
    "total_assets": {"total assets", "totalassets"},
    "total_liabilities": {
        "total liabilities",
        "totalliabilities",
        "total liabilities net minority interest",
    },
    "shareholders_equity": {
        "shareholders equity",
        "stockholders equity",
        "total equity",
        "owners equity",
        "stockholders equity",
        "common stock equity",
        "total equity gross minority interest",
    },
    "inventory": {"inventory", "inventories"},
    "cash": {"cash", "cash and cash equivalents"},
}


RATIO_LABELS = {
    "current_ratio": "Current Ratio",
    "quick_ratio": "Quick Ratio",
    "debt_to_equity": "Debt-to-Equity",
    "equity_ratio": "Equity Ratio",
    "gross_margin": "Gross Margin",
    "operating_margin": "Operating Margin",
    "net_margin": "Net Margin",
    "roa": "Return on Assets (ROA)",
    "roe": "Return on Equity (ROE)",
    "asset_turnover": "Asset Turnover",
}


def normalize_label(label: str) -> str:
    return " ".join(str(label).strip().lower().replace("_", " ").split())


def _safe_divide(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def _find_value(period_df: pd.DataFrame, canonical_name: str) -> float | None:
    aliases = ALIASES[canonical_name]
    matches = period_df.loc[period_df["line_item_normalized"].isin(aliases), "value"]
    if matches.empty:
        return None
    return float(matches.iloc[0])


def _average_with_previous(series: pd.Series, position: int) -> float | None:
    current = series.iloc[position]
    if pd.isna(current):
        return None
    if position == 0 or pd.isna(series.iloc[position - 1]):
        return float(current)
    return float((current + series.iloc[position - 1]) / 2)


def calculate_ratios(financials_long: pd.DataFrame) -> pd.DataFrame:
    periods = sorted(financials_long["period"].unique(), key=str)
    rows: list[dict[str, float | str | None]] = []

    assets_by_period = []
    equity_by_period = []

    for period in periods:
        period_df = financials_long[financials_long["period"] == period]
        assets_by_period.append(_find_value(period_df, "total_assets"))
        equity_by_period.append(_find_value(period_df, "shareholders_equity"))

    assets_series = pd.Series(assets_by_period, index=periods, dtype="float64")
    equity_series = pd.Series(equity_by_period, index=periods, dtype="float64")

    for index, period in enumerate(periods):
        period_df = financials_long[financials_long["period"] == period]
        revenue = _find_value(period_df, "revenue")
        cogs = _find_value(period_df, "cost_of_revenue")
        gross_profit = _find_value(period_df, "gross_profit")
        operating_income = _find_value(period_df, "operating_income")
        net_income = _find_value(period_df, "net_income")
        current_assets = _find_value(period_df, "current_assets")
        current_liabilities = _find_value(period_df, "current_liabilities")
        total_assets = assets_series.iloc[index]
        total_liabilities = _find_value(period_df, "total_liabilities")
        equity = equity_series.iloc[index]
        inventory = _find_value(period_df, "inventory")

        if gross_profit is None and revenue is not None and cogs is not None:
            gross_profit = revenue - cogs

        avg_assets = _average_with_previous(assets_series, index)
        avg_equity = _average_with_previous(equity_series, index)

        rows.extend(
            [
                {"period": period, "ratio": "current_ratio", "value": _safe_divide(current_assets, current_liabilities)},
                {
                    "period": period,
                    "ratio": "quick_ratio",
                    "value": _safe_divide(
                        None if current_assets is None else current_assets - (inventory or 0),
                        current_liabilities,
                    ),
                },
                {"period": period, "ratio": "debt_to_equity", "value": _safe_divide(total_liabilities, equity)},
                {"period": period, "ratio": "equity_ratio", "value": _safe_divide(equity, total_assets)},
                {"period": period, "ratio": "gross_margin", "value": _safe_divide(gross_profit, revenue)},
                {"period": period, "ratio": "operating_margin", "value": _safe_divide(operating_income, revenue)},
                {"period": period, "ratio": "net_margin", "value": _safe_divide(net_income, revenue)},
                {"period": period, "ratio": "roa", "value": _safe_divide(net_income, avg_assets)},
                {"period": period, "ratio": "roe", "value": _safe_divide(net_income, avg_equity)},
                {"period": period, "ratio": "asset_turnover", "value": _safe_divide(revenue, avg_assets)},
            ]
        )

    ratio_df = pd.DataFrame(rows)
    ratio_df["label"] = ratio_df["ratio"].map(RATIO_LABELS)
    return ratio_df


def calculate_trends(financials_long: pd.DataFrame) -> pd.DataFrame:
    pivot = financials_long.pivot_table(
        index="line_item",
        columns="period",
        values="value",
        aggfunc="first",
    )
    pivot = pivot.reindex(sorted(pivot.columns, key=str), axis=1)

    trend_rows: list[dict[str, str | float | None]] = []
    for line_item, row in pivot.iterrows():
        values = row.dropna()
        if len(values) < 2:
            continue
        first_value = float(values.iloc[0])
        last_value = float(values.iloc[-1])
        absolute_change = last_value - first_value
        percent_change = None if first_value == 0 else absolute_change / first_value
        direction = "Improving" if absolute_change > 0 else "Declining" if absolute_change < 0 else "Flat"
        trend_rows.append(
            {
                "line_item": line_item,
                "start_period": str(values.index[0]),
                "end_period": str(values.index[-1]),
                "start_value": first_value,
                "end_value": last_value,
                "absolute_change": absolute_change,
                "percent_change": percent_change,
                "direction": direction,
            }
        )

    return pd.DataFrame(trend_rows).sort_values(
        by="percent_change",
        ascending=False,
        na_position="last",
    )


@dataclass
class NarrativePoint:
    title: str
    detail: str


def build_narrative(financials_long: pd.DataFrame, ratio_df: pd.DataFrame) -> list[NarrativePoint]:
    periods = sorted(financials_long["period"].unique(), key=str)
    latest_period = periods[-1]
    previous_period = periods[-2] if len(periods) > 1 else None

    insights: list[NarrativePoint] = []

    def ratio_value(name: str, period: str) -> float | None:
        match = ratio_df[(ratio_df["ratio"] == name) & (ratio_df["period"] == period)]["value"]
        if match.empty or pd.isna(match.iloc[0]):
            return None
        return float(match.iloc[0])

    latest_roa = ratio_value("roa", latest_period)
    latest_roe = ratio_value("roe", latest_period)
    latest_current_ratio = ratio_value("current_ratio", latest_period)
    latest_margin = ratio_value("net_margin", latest_period)

    if latest_roe is not None and latest_roa is not None:
        insights.append(
            NarrativePoint(
                title="Profitability snapshot",
                detail=(
                    f"In {latest_period}, ROE was {latest_roe:.1%} and ROA was {latest_roa:.1%}, "
                    "showing how effectively equity and assets converted into profit."
                ),
            )
        )

    if latest_current_ratio is not None:
        liquidity_view = "comfortably above" if latest_current_ratio >= 1.5 else "slightly above" if latest_current_ratio >= 1 else "below"
        insights.append(
            NarrativePoint(
                title="Liquidity position",
                detail=(
                    f"The current ratio for {latest_period} was {latest_current_ratio:.2f}, which sits {liquidity_view} the 1.0 baseline."
                ),
            )
        )

    if previous_period and latest_margin is not None:
        previous_margin = ratio_value("net_margin", previous_period)
        if previous_margin is not None:
            change = latest_margin - previous_margin
            direction = "expanded" if change > 0 else "compressed" if change < 0 else "held steady"
            insights.append(
                NarrativePoint(
                    title="Margin trend",
                    detail=(
                        f"Net margin {direction} from {previous_margin:.1%} in {previous_period} "
                        f"to {latest_margin:.1%} in {latest_period}."
                    ),
                )
            )

    revenue_trend = calculate_trends(financials_long)
    revenue_row = revenue_trend[revenue_trend["line_item"].str.lower() == "revenue"]
    if not revenue_row.empty:
        row = revenue_row.iloc[0]
        pct = row["percent_change"]
        if pd.notna(pct):
            insights.append(
                NarrativePoint(
                    title="Revenue trajectory",
                    detail=(
                        f"Revenue moved from {row['start_value']:,.0f} in {row['start_period']} "
                        f"to {row['end_value']:,.0f} in {row['end_period']} ({pct:.1%})."
                    ),
                )
            )

    return insights
