"""Validation engine (Design doc §4.3).

Decides which rows are trustworthy enough for the summary report and records
why every other row is not. A row can fail more than one rule at a time, so
``_flag_reason`` may contain several reasons joined by "; ".
"""
from __future__ import annotations

import pandas as pd

from . import config

_BLANK_VALUES = {"", "nan", "none", "na", "n/a", "-", "—", "null"}


def _is_blank(series: pd.Series) -> pd.Series:
    """Boolean mask of cells that are empty or only whitespace."""
    as_str = series.astype("string").astype(str).str.strip().str.lower()
    return series.isna() | as_str.isin(_BLANK_VALUES)


def validate_required_fields(df: pd.DataFrame, required_columns: list[str]) -> pd.Series:
    """Mask of rows missing any required field (FR-VAL-01)."""
    missing = pd.Series(False, index=df.index)
    for col in required_columns:
        if col not in df.columns:
            missing = missing | pd.Series(True, index=df.index)
        else:
            missing = missing | _is_blank(df[col])
    return missing


def validate_required_fields_by_column(
    df: pd.DataFrame, required_columns: list[str]
) -> dict[str, pd.Series]:
    """Per-column masks of rows missing each required field (FR-VAL-01).

    Used to build a review table with one reason per missing field, because
    a row can fail more than one rule at a time (Design doc §4.3).
    """
    masks: dict[str, pd.Series] = {}
    for col in required_columns:
        if col not in df.columns:
            mask = pd.Series(True, index=df.index)
        else:
            mask = _is_blank(df[col])
        if mask.any():
            masks[f"Missing required field ({col})"] = mask
    return masks


def _original_nonempty(mapped_df: pd.DataFrame, col: str) -> pd.Series:
    """Cells that had a real value before cleaning (used for type checks).

    If the column is absent from the mapped frame, treat every cell as
    "not originally present" so we don't double-flag with required-field.
    """
    if col not in mapped_df.columns:
        return pd.Series(False, index=mapped_df.index)
    return ~_is_blank(mapped_df[col])


def validate_types(
    cleaned_df: pd.DataFrame,
    mapped_df: pd.DataFrame,
    numeric_columns: list[str] | None = None,
    date_columns: list[str] | None = None,
) -> dict[str, pd.Series]:
    """Masks of rows whose values could not be coerced during cleaning.

    A value is a type error only if it was non-empty in the original input
    but became NaN/NaT after cleaning (FR-VAL-02).
    """
    numeric_columns = numeric_columns or config.NUMERIC_COLUMNS
    date_columns = date_columns or config.DATE_COLUMNS
    masks: dict[str, pd.Series] = {}

    for col in numeric_columns:
        if col in cleaned_df.columns:
            bad = cleaned_df[col].isna() & _original_nonempty(mapped_df, col)
            if bad.any():
                masks[f"Invalid amount ({col})"] = bad
    for col in date_columns:
        if col in cleaned_df.columns:
            bad = cleaned_df[col].isna() & _original_nonempty(mapped_df, col)
            if bad.any():
                masks[f"Invalid date ({col})"] = bad
    return masks


def build_review_table(df: pd.DataFrame, reason_masks: dict[str, pd.Series]) -> pd.DataFrame:
    """Combine all failure masks into one flagged-rows DataFrame.

    Adds a ``_flag_reason`` column listing every rule the row failed
    (FR-VAL-03). Rows that fail nothing are not included.
    """
    reasons: dict[str, pd.Series] = {}
    combined = pd.Series(False, index=df.index)
    for reason, mask in reason_masks.items():
        m = mask.reindex(df.index).fillna(False).astype(bool)
        combined = combined | m
        reasons[reason] = m

    flagged = df.loc[combined].copy()
    if flagged.empty:
        return flagged

    flagged["_flag_reason"] = [
        "; ".join(r for r, m in reasons.items() if bool(m.loc[idx])) for idx in flagged.index
    ]
    # Keep the original position inside the cleaned dataset for traceability
    # and for a correct split later (indices are reset from here on).
    flagged.insert(0, "_source_row", flagged.index)
    return flagged.reset_index(drop=True)


def split_clean_and_flagged(df: pd.DataFrame, flagged_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (clean rows, flagged rows) (Design doc §4.3).

    Flagged rows are excluded from reporting by default (FR-VAL-05).
    """
    if flagged_df.empty:
        return df.reset_index(drop=True), flagged_df
    if "_source_row" in flagged_df.columns:
        flagged_rows = set(flagged_df["_source_row"].tolist())
    else:
        flagged_rows = set(flagged_df.index)
    clean_indices = [i for i in df.index if i not in flagged_rows]
    return df.loc[clean_indices].reset_index(drop=True), flagged_df