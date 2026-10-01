"""Convert DataFrames into JSON-safe structures.

Pandas uses ``NaN``/``NaT`` for missing values and can hold ``inf``; neither
serializes to JSON. These helpers normalize every cell so API responses are
always valid JSON with ``null`` for missing values (PRD §8.3).
"""
from __future__ import annotations

import math

import pandas as pd


def clean_value(value):
    """Normalize one cell into a JSON-safe Python value."""
    if value is None:
        return None
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    if isinstance(value, (int, str, bool)):
        return value
    if hasattr(value, "isoformat"):  # Timestamps, dates, timedeltas
        return value.isoformat()
    return str(value)


def records_from_df(df: pd.DataFrame) -> list[dict]:
    """Return the DataFrame as a list of dicts with JSON-safe values."""
    if df is None or df.empty:
        return []
    rows = df.where(pd.notna(df), None).to_dict(orient="records")
    return [{str(k): clean_value(v) for k, v in row.items()} for row in rows]