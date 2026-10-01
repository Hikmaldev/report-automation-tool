"""Reporting layer (Design doc §4.4).

Turns the clean dataset into summary tables and chart-ready data. This module
only ever reads the clean subset — flagged rows never appear unless the UI
explicitly opts in (FR-VAL-05).
"""
from __future__ import annotations

import pandas as pd

from . import config


def build_summary(
    df: pd.DataFrame,
    group_by: str,
    aggregate_column: str,
    aggregate_func: str = "sum",
) -> pd.DataFrame:
    """Group ``df`` by ``group_by`` and aggregate ``aggregate_column``.

    Raises ValueError with a plain-language message for invalid choices.
    """
    if group_by not in df.columns:
        raise ValueError(f"Group column '{group_by}' was not found in the clean dataset.")
    if aggregate_column not in df.columns:
        raise ValueError(f"Aggregate column '{aggregate_column}' was not found in the clean dataset.")
    if aggregate_func not in config.AGGREGATE_FUNCTIONS.values():
        raise ValueError("Unsupported aggregate function.")

    grouped = df.groupby(group_by, dropna=False)[aggregate_column]
    try:
        result = grouped.agg(aggregate_func)
    except TypeError as exc:
        friendly = {
            "sum": "Summing requires a numeric column — try Revenue or Quantity instead.",
            "mean": "Averaging requires a numeric column — try Revenue or Quantity instead.",
        }.get(aggregate_func, str(exc))
        raise ValueError(friendly) from exc
    except ValueError as exc:
        raise ValueError("Column selection is invalid for this function.") from exc

    summary = result.rename(aggregate_column).reset_index()
    summary[group_by] = summary[group_by].astype(str)
    return summary


def build_chart_data(summary_df: pd.DataFrame) -> pd.DataFrame:
    """Return chart-ready (labels, values) from a summary DataFrame."""
    if summary_df.empty:
        return summary_df
    return summary_df.copy()