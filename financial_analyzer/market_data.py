from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from financial_analyzer.metrics import normalize_label


STATEMENT_MAP = {
    "income_statement": [
        "income_stmt",
        "financials",
        "quarterly_income_stmt",
        "quarterly_financials",
    ],
    "balance_sheet": [
        "balance_sheet",
        "quarterly_balance_sheet",
    ],
    "cash_flow": [
        "cashflow",
        "cash_flow",
        "quarterly_cashflow",
        "quarterly_cash_flow",
    ],
}


LABEL_OVERRIDES = {
    "totalrevenue": "Revenue",
    "costofrevenue": "Cost Of Revenue",
    "grossprofit": "Gross Profit",
    "operatingincome": "Operating Income",
    "netincome": "Net Income",
    "currentassets": "Current Assets",
    "currentliabilities": "Current Liabilities",
    "inventory": "Inventory",
    "cashandcashequivalents": "Cash",
    "cashcashequivalentsandshortterminvestments": "Cash",
    "totalassets": "Total Assets",
    "totalliabilitiesnetminorityinterest": "Total Liabilities",
    "stockholdersequity": "Shareholders Equity",
    "commonstockequity": "Shareholders Equity",
}


@dataclass
class MarketBundle:
    financials_long: pd.DataFrame
    summary: dict[str, object]
    price_history: pd.DataFrame
    news: list[dict[str, object]]


def fetch_ticker_bundle(ticker_symbol: str) -> MarketBundle:
    try:
        import yfinance as yf
    except ModuleNotFoundError as exc:
        raise ValueError("Yahoo Finance mode requires the `yfinance` package. Run `pip install -r requirements.txt`.") from exc

    ticker = yf.Ticker(ticker_symbol.strip().upper())

    frames = []
    for statement_name, attrs in STATEMENT_MAP.items():
        statement_df = _first_non_empty_frame(ticker, attrs)
        if statement_df is None:
            continue
        frames.append(_statement_to_long(statement_df, statement_name))

    if not frames:
        raise ValueError("No financial statements were returned for this ticker.")

    financials_long = pd.concat(frames, ignore_index=True)
    info = getattr(ticker, "info", {}) or {}
    fast_info = getattr(ticker, "fast_info", {}) or {}
    history = ticker.history(period="1y", interval="1d").reset_index()
    news = getattr(ticker, "news", []) or []

    summary = {
        "ticker": ticker_symbol.strip().upper(),
        "longName": info.get("longName") or info.get("shortName") or ticker_symbol.strip().upper(),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "currency": info.get("currency"),
        "currentPrice": info.get("currentPrice") or fast_info.get("lastPrice"),
        "marketCap": info.get("marketCap"),
        "trailingPE": info.get("trailingPE"),
        "forwardPE": info.get("forwardPE"),
        "dividendYield": info.get("dividendYield"),
        "targetMeanPrice": (info.get("targetMeanPrice") if isinstance(info, dict) else None),
    }

    return MarketBundle(
        financials_long=financials_long,
        summary=summary,
        price_history=history,
        news=news[:5],
    )


def _first_non_empty_frame(ticker, attrs: list[str]) -> pd.DataFrame | None:
    for attr in attrs:
        value = getattr(ticker, attr, None)
        if isinstance(value, pd.DataFrame) and not value.empty:
            return value
    return None


def _statement_to_long(frame: pd.DataFrame, statement_name: str) -> pd.DataFrame:
    working = frame.copy()
    if working.empty:
        return pd.DataFrame(columns=["statement", "line_item", "period", "value", "line_item_normalized"])

    if working.index.name is None:
        working.index.name = "line_item"
    working = working.reset_index()
    line_item_column = working.columns[0]
    long_df = working.melt(id_vars=[line_item_column], var_name="period", value_name="value")
    long_df = long_df.dropna(subset=["value"])
    long_df["statement"] = statement_name
    long_df["line_item"] = long_df[line_item_column].map(_pretty_label)
    long_df["line_item_normalized"] = long_df["line_item"].map(normalize_label)
    long_df["period"] = long_df["period"].map(_format_period)
    long_df["value"] = pd.to_numeric(long_df["value"], errors="coerce")
    long_df = long_df.dropna(subset=["value"])
    return long_df[["statement", "line_item", "period", "value", "line_item_normalized"]]


def _format_period(value) -> str:
    if hasattr(value, "year"):
        return str(value.year)
    text = str(value)
    return text[:10]


def _pretty_label(value: object) -> str:
    raw = str(value).strip()
    collapsed = "".join(char for char in raw if char.isalnum()).lower()
    if collapsed in LABEL_OVERRIDES:
        return LABEL_OVERRIDES[collapsed]
    spaced = []
    for index, char in enumerate(raw):
        if index > 0 and char.isupper() and raw[index - 1].islower():
            spaced.append(" ")
        spaced.append(char)
    return "".join(spaced).replace("_", " ").strip().title()
