"""Ingestion layer (Design doc §4.1).

Turns uploaded files into clean, in-memory DataFrames tagged with their
source file name. File-level errors (corrupt file, unsupported extension,
too large) are reported separately from row-level validation errors.
"""
from __future__ import annotations

import csv
import io
import os

import pandas as pd

from . import config

# Convenience alias: the traceability column added during ingestion.
NORMALIZED_HEADER = config.NORMALIZED_HEADER


def normalize_name(name: str) -> str:
    """Normalize a column name for mapping lookups (lowercase, collapse spaces)."""
    return " ".join(str(name).strip().lower().split())


def detect_extension(filename: str) -> str:
    """Return the lowercase file extension, e.g. '.csv'."""
    return os.path.splitext(filename or "")[1].lower()


def read_csv_flexible(file_obj) -> pd.DataFrame:
    """Read a CSV, tolerating encoding problems and common delimiters."""
    raw = file_obj.getvalue() if hasattr(file_obj, "getvalue") else file_obj.read()
    text = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw.decode("utf-8", errors="replace")

    sample = "\n".join(text.splitlines()[:10])
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        delimiter = ","

    # Verify the table shape with Python's csv parser BEFORE pandas runs:
    # pandas' python engine can "succeed" on a mismatched file by shifting
    # values into an implicit index instead of raising, which would corrupt
    # the report invisibly. Report the row instead (PRD §8.2, "never silently
    # discard data"). csv.reader understands quoting, so properly quoted
    # values like "$1,240.00" do not false-positive.
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    rows = [r for r in rows if r and not (len(r) == 1 and not r[0].strip())]
    if not rows:
        raise ValueError("The file is empty or has no readable data rows.")
    expected_cols = len(rows[0])
    for idx, row in enumerate(rows[1:], start=2):
        if len(row) != expected_cols:
            raise ValueError(
                f"Row {idx} has {len(row)} column(s) but the header declares "
                f"{expected_cols}. Check for unquoted commas or stray separators "
                "in the file."
            )

    df = pd.read_csv(io.StringIO(text), sep=delimiter, encoding="utf-8", engine="python")
    if len(df.columns) != expected_cols:  # belt-and-suspenders
        raise ValueError(
            f"Column count mismatch: the header declares {expected_cols} column(s) "
            f"but the data contains {len(df.columns)}."
        )
    return df


def read_uploaded_file(uploaded_file) -> pd.DataFrame:
    """Parse one uploaded file into a DataFrame tagged with its source name.

    Raises:
        ValueError: unsupported extension (FR-UP-02).
        Exception: any parse failure for a supported file, caught per-file
            by :func:`read_multiple_files`.
    """
    filename = uploaded_file.name
    ext = detect_extension(filename)
    if ext not in config.SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. Only {', '.join(sorted(config.SUPPORTED_EXTENSIONS))} are accepted."
        )

    if ext == ".xlsx":
        df = pd.read_excel(uploaded_file, engine="openpyxl", sheet_name=0)
    else:
        df = read_csv_flexible(uploaded_file)

    # Normalize headers and drop blank rows/columns before anything else.
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, df.columns != ""]
    df = df.dropna(how="all").reset_index(drop=True)

    df[NORMALIZED_HEADER] = filename
    return df


def read_multiple_files(
    files,
    max_file_size_mb: int = config.MAX_FILE_SIZE_MB,
    max_total_mb: int = config.MAX_TOTAL_UPLOAD_MB,
) -> tuple[list[dict], list[dict]]:
    """Parse a batch of files, collecting per-file errors without stopping.

    Returns:
        (records, errors)
        records: list of dicts {"name", "df", "rows", "columns", "size_bytes"}.
        errors:  list of dicts {"file", "message"} in plain language.
    """
    records: list[dict] = []
    errors: list[dict] = []
    total_bytes = 0

    for f in files:
        ext = detect_extension(f.name)
        if ext not in config.SUPPORTED_EXTENSIONS:
            errors.append(
                {
                    "file": f.name,
                    "message": "Unsupported file type. Please upload .xlsx or .csv files only.",
                }
            )
            continue
        if f.size / 1_000_000 > max_file_size_mb:
            errors.append(
                {"file": f.name, "message": f"File is larger than {max_file_size_mb} MB and was skipped."}
            )
            continue
        total_bytes += f.size
        try:
            df = read_uploaded_file(f)
        except Exception as exc:  # noqa: BLE001 - reported to the user, never raised
            errors.append({"file": f.name, "message": f"This file could not be read: {exc}"})
            continue

        records.append(
            {
                "name": f.name,
                "df": df,
                "rows": int(len(df)),
                "columns": [c for c in df.columns if c != NORMALIZED_HEADER],
                "size_bytes": int(f.size),
            }
        )

    if total_bytes / 1_000_000 > max_total_mb:
        errors.append(
            {"file": "(whole session)", "message": f"Total upload exceeds {max_total_mb} MB."}
        )

    return records, errors


def build_mapping_frame(records: list[dict]) -> pd.DataFrame:
    """Build a unique, deduplicated view of every source column found.

    Each row is one source column with a recommended standard field from
    ``config.DEFAULT_COLUMN_MAP``, the files it appears in, and an example
    value. This frame drives the column-mapping screener (FR-CLN-06).
    """
    rows = []
    for rec in records:
        for col in rec["columns"]:
            example = None
            for value in rec["df"][col].dropna().astype(str):
                if value.strip():
                    example = value.strip()[:28]
                    break
            rows.append(
                {
                    "source_column": col,
                    "standard_field": config.DEFAULT_COLUMN_MAP.get(normalize_name(col), ""),
                    "files": rec["name"],
                    "example": example or "",
                }
            )

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame

    # One row per unique source column: list files, keep the first example.
    grouped = (
        frame.groupby("source_column")
        .agg(
            standard_field=("standard_field", "first"),
            example=("example", "first"),
            files=("files", lambda s: ", ".join(sorted(set(s)))),
        )
        .reset_index()
    )
    grouped["standard_field"] = grouped["standard_field"].fillna("")
    return grouped


def apply_mapping(records: list[dict], column_map: dict) -> pd.DataFrame:
    """Rename source columns to their standard fields and concatenate.

    Columns mapped to ``IGNORE_LABEL`` or left blank are dropped from the
    combined dataset (Design doc §4.1 / FR-CLN-06). The ``_source_file``
    column is always kept for traceability.
    """
    canonical = {v for v in column_map.values() if v and v != config.IGNORE_LABEL}
    frames = []
    for rec in records:
        df = rec["df"]
        rename = {src: std for src, std in column_map.items() if std in canonical and src in df.columns}
        mapped = df.rename(columns=rename)
        keep = [c for c in mapped.columns if c == NORMALIZED_HEADER or c in canonical]
        frames.append(mapped[keep])

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def missing_required_columns(column_map: dict) -> list[str]:
    """Return required canonical fields that no source column maps to."""
    mapped = {v for v in column_map.values() if v and v != config.IGNORE_LABEL}
    return [c for c in config.REQUIRED_COLUMNS if c not in mapped]