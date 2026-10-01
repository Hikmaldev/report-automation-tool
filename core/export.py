"""Export layer (Design doc §4.5).

Turns DataFrames back into downloadable bytes — everything happens in memory
via io.BytesIO, nothing touches disk.
"""
from __future__ import annotations

import io

import pandas as pd


def to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Data") -> bytes:
    """Write a DataFrame into an in-memory .xlsx file (openpyxl)."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    return buffer.getvalue()


def to_excel_with_sheets(sheets: dict[str, pd.DataFrame]) -> bytes:
    """Write multiple named DataFrames as sheets in one .xlsx."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, index=False, sheet_name=name[:31])
    return buffer.getvalue()


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Write a DataFrame into an in-memory UTF-8 CSV string."""
    return df.to_csv(index=False).encode("utf-8-sig")


def build_download_bundle(
    clean_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    flagged_df: pd.DataFrame,
) -> dict[str, bytes]:
    """Produce every downloadable artifact in one call (Download Center)."""
    return {
        "cleaned_xlsx": to_excel_bytes(clean_df, sheet_name="Clean data"),
        "cleaned_csv": to_csv_bytes(clean_df),
        "summary_xlsx": to_excel_with_sheets(
            {"Summary": summary_df, "Chart data": summary_df}
        ),
        "flagged_xlsx": to_excel_bytes(flagged_df, sheet_name="Flagged rows"),
        "flagged_csv": to_csv_bytes(flagged_df),
    }