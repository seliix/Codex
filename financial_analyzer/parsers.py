from __future__ import annotations

import io
import re
from typing import Iterable

import pandas as pd

from financial_analyzer.metrics import normalize_label


CANONICAL_STATEMENTS = {
    "income statement": "income_statement",
    "income_statement": "income_statement",
    "balance sheet": "balance_sheet",
    "balance_sheet": "balance_sheet",
    "cash flow": "cash_flow",
    "cash_flow": "cash_flow",
}


def parse_uploaded_file(uploaded_file) -> pd.DataFrame:
    file_name = uploaded_file.name.lower()
    if file_name.endswith(".csv"):
        return _reshape_structured_frame(pd.read_csv(uploaded_file))
    if file_name.endswith((".xlsx", ".xls")):
        workbook = pd.read_excel(uploaded_file, sheet_name=None)
        frames = []
        for sheet_name, frame in workbook.items():
            reshaped = _reshape_structured_frame(frame, inferred_statement=sheet_name)
            if not reshaped.empty:
                frames.append(reshaped)
        if not frames:
            raise ValueError("No supported financial tables were found in the spreadsheet.")
        return pd.concat(frames, ignore_index=True)
    if file_name.endswith(".pdf"):
        return _parse_pdf(uploaded_file)
    raise ValueError("Unsupported file format. Upload CSV, Excel, or PDF.")


def _reshape_structured_frame(frame: pd.DataFrame, inferred_statement: str | None = None) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["statement", "line_item", "period", "value", "line_item_normalized"])

    cleaned = frame.copy()
    cleaned.columns = [str(column).strip() for column in cleaned.columns]
    cleaned = cleaned.dropna(how="all").dropna(axis=1, how="all")

    statement_column = next((column for column in cleaned.columns if normalize_label(column) == "statement"), None)
    line_item_column = next(
        (column for column in cleaned.columns if normalize_label(column) in {"line item", "line_item", "account", "metric"}),
        None,
    )

    if line_item_column is None:
        if cleaned.shape[1] >= 2:
            line_item_column = cleaned.columns[0]
        else:
            return pd.DataFrame(columns=["statement", "line_item", "period", "value", "line_item_normalized"])

    period_columns = [column for column in cleaned.columns if column not in {statement_column, line_item_column}]
    if not period_columns:
        return pd.DataFrame(columns=["statement", "line_item", "period", "value", "line_item_normalized"])

    if statement_column is None:
        inferred = CANONICAL_STATEMENTS.get(normalize_label(inferred_statement or ""), "income_statement")
        cleaned["statement"] = inferred
        statement_column = "statement"
    else:
        cleaned[statement_column] = cleaned[statement_column].map(
            lambda value: CANONICAL_STATEMENTS.get(normalize_label(value), "income_statement")
        )

    melted = cleaned.melt(
        id_vars=[statement_column, line_item_column],
        value_vars=period_columns,
        var_name="period",
        value_name="value",
    )
    melted = melted.rename(columns={statement_column: "statement", line_item_column: "line_item"})
    melted["value"] = melted["value"].apply(_to_number)
    melted = melted.dropna(subset=["value"])
    melted["period"] = melted["period"].astype(str).str.strip()
    melted["line_item"] = melted["line_item"].astype(str).str.strip()
    melted["line_item_normalized"] = melted["line_item"].map(normalize_label)
    return melted[["statement", "line_item", "period", "value", "line_item_normalized"]]


def _parse_pdf(uploaded_file) -> pd.DataFrame:
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError as exc:
        raise ValueError("PDF support requires the `pypdf` package. Run `pip install -r requirements.txt`.") from exc

    data = uploaded_file.read()
    reader = PdfReader(io.BytesIO(data))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    period_candidates = []
    for line in lines:
        period_candidates.extend(re.findall(r"\b(?:20\d{2}|19\d{2})\b", line))
    periods = list(dict.fromkeys(period_candidates))
    if not periods:
        raise ValueError("Could not detect year columns in the PDF. Try Excel/CSV for best results.")

    pattern = re.compile(
        rf"^(?P<line_item>[A-Za-z][A-Za-z&,\-()/ ]+?)\s+(?P<values>{'\\s+'.join([r'[-(]?\$?[\d,]+(?:\.\d+)?\)?' for _ in periods])})$"
    )

    rows: list[dict[str, str | float]] = []
    current_statement = "income_statement"
    for line in lines:
        normalized = normalize_label(line)
        if normalized in CANONICAL_STATEMENTS:
            current_statement = CANONICAL_STATEMENTS[normalized]
            continue
        match = pattern.match(line)
        if not match:
            continue
        values = re.findall(r"[-(]?\$?[\d,]+(?:\.\d+)?\)?", match.group("values"))
        if len(values) != len(periods):
            continue
        for period, value in zip(periods, values, strict=True):
            numeric_value = _to_number(value)
            if numeric_value is None:
                continue
            line_item = match.group("line_item").strip()
            rows.append(
                {
                    "statement": current_statement,
                    "line_item": line_item,
                    "period": str(period),
                    "value": numeric_value,
                    "line_item_normalized": normalize_label(line_item),
                }
            )

    if not rows:
        raise ValueError(
            "The PDF parser could not extract a tabular statement. Upload an Excel/CSV export or a simpler text-based PDF."
        )

    return pd.DataFrame(rows)


def _to_number(value) -> float | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    cleaned = text.replace("$", "").replace(",", "").replace("(", "").replace(")", "")
    try:
        number = float(cleaned)
    except ValueError:
        return None
    return -number if negative else number
