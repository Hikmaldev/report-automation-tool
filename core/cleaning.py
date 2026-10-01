"""Deterministic, rule-based cleaning (Design doc §4.2).

Cleaning never deletes a row because of a bad value. It converts bad values
to missing (NaN/NaT); deciding whether a missing value means "flag the row"
is the validation engine's job, not this module's.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from . import config

_STRIP_PATTERN = re.compile(r"[^\d,.\-+()eE\s]")


def _clean_numeric_string(value) -> str:
    """Normalize one value into a float-parseable string, or return ''."""
    if value is None or pd.isna(value):
        return ""
    s = str(value).strip().replace("\u00a0", " ")
    if s in ("", "-", "—", "na", "n/a", "none"):
        return ""
    # Parenthesized negatives: (840) -> -840
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1].strip()
    # Strip currency symbols / stray letters.
    s = _STRIP_PATTERN.sub("", s).strip()
    if not s:
        return ""

    # Handle thousand/decimal separators using the classic heuristic:
    # the right-most separator is the decimal separator when both are used.
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        # A trailing group of exactly 3 digits strongly suggests thousands.
        if len(parts[-1]) == 3 and len(parts) <= 4:
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    elif s.count(".") >= 1:
        parts = s.split(".")
        # "1.240" style thousands only if all-but-last groups are 1-3 digits.
        if len(parts[-1]) == 3 and all(1 <= len(p) <= 3 for p in parts[:-1]):
            s = s.replace(".", "")
    return s


def _to_float(value) -> float:
    s = _clean_numeric_string(value)
    if not s:
        return np.nan
    try:
        return float(s)
    except ValueError:
        return np.nan


def deduplicate(df: pd.DataFrame, subset: list[str] | None = None) -> tuple[pd.DataFrame, int]:
    """Drop exact duplicate rows based on mapped columns (FR-CLN-01).

    The ``_source_file`` column is intentionally excluded: two identical rows
    uploaded from different files are still duplicates (Business rule 1).
    """
    before = len(df)
    target = subset or [c for c in df.columns if c != config.NORMALIZED_HEADER]
    deduped = df.drop_duplicates(subset=target, keep="first").reset_index(drop=True)
    return deduped, before - len(deduped)


def standardize_dates(df: pd.DataFrame, date_columns: list[str], log: dict | None = None) -> pd.DataFrame:
    """Parse date columns and reformat to YYYY-MM-DD (FR-CLN-02).

    Unparseable values become NaT; validation flags those rows later.
    """
    for col in date_columns:
        if col not in df.columns:
            continue
        original = df[col]
        nonempty = original.notna() & original.astype("string").astype(str).str.strip().ne("")

        try:
            parsed = pd.to_datetime(original, errors="coerce", format="mixed")
        except (TypeError, ValueError):
            parsed = pd.to_datetime(original, errors="coerce")

        # Day-first fallback (e.g. "31/09/2026") when plain parsing struggles.
        if nonempty.any() and parsed[nonempty].isna().mean() > 0.25:
            try:
                parsed_df = pd.to_datetime(original, errors="coerce", format="mixed", dayfirst=True)
            except (TypeError, ValueError):
                parsed_df = pd.to_datetime(original, errors="coerce", dayfirst=True)
            if parsed_df[nonempty].notna().sum() > parsed[nonempty].notna().sum():
                parsed = parsed_df

        df[col] = parsed.dt.strftime("%Y-%m-%d").where(parsed.notna())
        if log is not None:
            log["dates"] = log.get("dates", 0) + int(nonempty.sum())
            log["date_parse_failed"] = log.get("date_parse_failed", 0) + int(
                (nonempty & parsed.isna()).sum()
            )
    return df


def standardize_numbers(df: pd.DataFrame, numeric_columns: list[str], log: dict | None = None) -> pd.DataFrame:
    """Strip currency symbols and separators, cast to numeric (FR-CLN-03).

    Invalid values become NaN instead of crashing the pipeline.
    """
    for col in numeric_columns:
        if col not in df.columns:
            continue
        original = df[col]
        nonempty = original.notna() & original.astype("string").astype(str).str.strip().ne("")
        cleaned = original.map(_to_float)
        df[col] = cleaned
        if log is not None:
            log["numbers"] = log.get("numbers", 0) + int(nonempty.sum())
            failures = int((nonempty & cleaned.isna()).sum())
            if failures:
                log["number_parse_failed"] = log.get("number_parse_failed", 0) + failures
    return df


def standardize_text(
    df: pd.DataFrame,
    text_columns: list[str],
    casing_columns: list[str] | None = None,
    log: dict | None = None,
) -> pd.DataFrame:
    """Trim whitespace and apply consistent casing where configured."""
    for col in text_columns:
        if col not in df.columns:
            continue
        original = df[col].astype("string").astype(str)
        trimmed = original.str.strip()
        changed = int((trimmed != original).sum())
        df[col] = df[col].map(lambda x: x.strip() if isinstance(x, str) else x)
        if log is not None and changed:
            log["whitespace_trimmed"] = log.get("whitespace_trimmed", 0) + changed

    for col in casing_columns or []:
        if col in df.columns:
            before = df[col].astype("string").astype(str)
            df[col] = df[col].map(lambda x: x.title() if isinstance(x, str) else x)
            if log is not None:
                changed = int((df[col].astype("string").astype(str) != before).sum())
                if changed:
                    log["casing_standardized"] = log.get("casing_standardized", 0) + changed
    return df


def run_cleaning_pipeline(df: pd.DataFrame, cfg=None) -> tuple[pd.DataFrame, dict]:
    """Run deduplication and format standardization in order (FR-CLN-07).

    Returns (cleaned_df, log) where log summarizes every automatic change.
    """
    cfg = cfg or config
    log: dict = {"duplicates_removed": 0}
    df = df.copy()

    df, log["duplicates_removed"] = deduplicate(df)
    df = standardize_dates(df, cfg.DATE_COLUMNS, log)
    df = standardize_numbers(df, cfg.NUMERIC_COLUMNS, log)
    df = standardize_text(df, cfg.TEXT_COLUMNS, cfg.CASING_COLUMNS, log)
    return df, log