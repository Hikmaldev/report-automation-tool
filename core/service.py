"""Unified service facade for every frontend screen (Design doc §11).

Pages never import the pipeline modules directly anymore — they go through
this layer, which has two interchangeable backends:

* **local** (default) — the classic in-process pipeline. Works anywhere a
  single Streamlit process runs, including Streamlit Cloud, where no
  secondary server can be hosted.
* **api** — delegates every operation to the Flask backend over HTTP. Enabled
  automatically when ``REPORT_API_URL`` is set (e.g. ``http://localhost:5000``)
  and the backend answers ``/api/health``. ``REPORT_API_MODE=api|local`` forces
  a choice instead of auto-detection.

Both modes return exactly the same shapes (DataFrames, dicts), so the pages
do not know which backend is active.
"""
from __future__ import annotations

import os
import urllib.parse
import uuid

import pandas as pd
import requests

from . import cleaning, config, export as core_export, ingestion, reporting, validation

URL_KEY = "REPORT_API_URL"
MODE_KEY = "REPORT_API_MODE"
TIMEOUT = 30.0
_HEALTH_TIMEOUT = 2.0

_state: dict = {"base": None, "mode": None, "probe_error": None}


class ReportServiceError(ValueError):
    """A user-safe service failure (subclasses ValueError so pages that
    already handle ``ValueError`` keep working in both modes)."""


def clear_cache() -> None:
    """Forget the resolved mode/URL (used by tests and after config changes)."""
    _state.update({"base": None, "mode": None, "probe_error": None})


# --------------------------------------------------------------------------- #
# Mode resolution
# --------------------------------------------------------------------------- #
def api_base_url() -> str | None:
    if _state["base"] is None:
        _state["base"] = (os.environ.get(URL_KEY) or "").strip().rstrip("/") or None
    return _state["base"]


def backend_mode() -> str:
    """Return 'api' or 'local'; resolved once per process."""
    if _state["mode"] is None:
        choice = (os.environ.get(MODE_KEY) or "auto").strip().lower()
        if choice == "api":
            _state["mode"] = "api"
        elif choice == "local":
            _state["mode"] = "local"
        else:  # auto: use the API only if it is actually reachable
            base = api_base_url()
            if base:
                try:
                    requests.get(f"{base}/api/health", timeout=_HEALTH_TIMEOUT).raise_for_status()
                    _state["mode"] = "api"
                except Exception as exc:  # noqa: BLE001 - fall back to local
                    _state["mode"] = "local"
                    _state["probe_error"] = str(exc)
            else:
                _state["mode"] = "local"
    return _state["mode"]


def backend_info() -> dict:
    """Status shown in the UI footer: mode, URL, and any probe error."""
    return {"mode": backend_mode(), "url": api_base_url(), "error": _state["probe_error"]}


# --------------------------------------------------------------------------- #
# HTTP plumbing
# --------------------------------------------------------------------------- #
def _detail(response: requests.Response) -> str:
    try:
        payload = response.json()
        return payload.get("error", f"Request failed with status {response.status_code}.")
    except ValueError:
        return f"Request failed with status {response.status_code}."


def _get(url: str, **kwargs) -> requests.Response:
    response = requests.get(url, timeout=kwargs.pop("timeout", TIMEOUT), **kwargs)
    if response.status_code >= 400:
        raise ReportServiceError(_detail(response))
    return response


def _post(url: str, **kwargs) -> requests.Response:
    response = requests.post(url, timeout=kwargs.pop("timeout", TIMEOUT), **kwargs)
    if response.status_code >= 400:
        raise ReportServiceError(_detail(response))
    return response


def _put(url: str, **kwargs) -> requests.Response:
    response = requests.put(url, timeout=kwargs.pop("timeout", TIMEOUT), **kwargs)
    if response.status_code >= 400:
        raise ReportServiceError(_detail(response))
    return response


def _delete(url: str, **kwargs) -> requests.Response:
    response = requests.delete(url, timeout=kwargs.pop("timeout", TIMEOUT), **kwargs)
    if response.status_code >= 400 and response.status_code != 404:
        raise ReportServiceError(_detail(response))
    return response


def _frame_from_columns_rows(body: dict) -> pd.DataFrame:
    columns, rows = body.get("columns", []), body.get("rows", [])
    if not columns:
        return pd.DataFrame()
    return pd.DataFrame(rows, columns=columns)


# --------------------------------------------------------------------------- #
# Session lifecycle
# --------------------------------------------------------------------------- #
def new_session() -> str:
    """Create a server-side session (API mode) or a local id (local mode)."""
    if backend_mode() == "api":
        return _post(f"{api_base_url()}/api/sessions").json()["session_id"]
    return uuid.uuid4().hex


def reset_session(sid: str | None) -> None:
    """Discard all data on the backend (local mode: nothing to do)."""
    if backend_mode() == "api" and sid:
        try:
            _post(f"{api_base_url()}/api/sessions/{sid}/reset")
        except ReportServiceError:
            pass


# --------------------------------------------------------------------------- #
# Upload (FR-UP-01 … 05)
# --------------------------------------------------------------------------- #
def upload_files(sid: str, files) -> tuple[list[dict], list[dict]]:
    """Parse one batch of uploads. ``files`` are file-likes with ``.name``,
    ``.size`` and either ``.getvalue()`` or readable bytes.

    Returns ``(records, errors)`` with the same shape as before, so pages are
    unchanged. In API mode records carry no local DataFrame (``df=None``) —
    the authoritative copies live on the backend.
    """
    if backend_mode() == "api":
        payload = [
            ("files", (f.name, f.getvalue(), "application/octet-stream"))
            for f in files
            if getattr(f, "name", None)
        ]
        body = _post(f"{api_base_url()}/api/sessions/{sid}/files", files=payload).json()
        records = [
            {
                "name": f["name"],
                "rows": f["rows"],
                "columns": f["columns"],
                "size_bytes": f["size_bytes"],
                "df": None,
            }
            for f in body.get("files", [])
        ]
        return records, body.get("errors", [])
    return ingestion.read_multiple_files(files)


def remove_file(sid: str, filename: str) -> None:
    """Tell the backend to forget a file (local mode: a no-op, pages filter
    their own session list)."""
    if backend_mode() == "api" and sid:
        quoted = urllib.parse.quote(filename, safe="")
        _delete(f"{api_base_url()}/api/sessions/{sid}/files/{quoted}")


# --------------------------------------------------------------------------- #
# Mapping (FR-CLN-06)
# --------------------------------------------------------------------------- #
def mapping_frame(sid: str, records: list[dict] | None = None) -> pd.DataFrame:
    """Suggested source-column -> standard-field table for the screener."""
    if backend_mode() == "api":
        rows = _get(f"{api_base_url()}/api/sessions/{sid}/mapping").json().get("columns", [])
        columns = list(rows[0].keys()) if rows else []
        return pd.DataFrame(rows, columns=columns) if columns else pd.DataFrame()
    return ingestion.build_mapping_frame(records or [])


def apply_mapping(sid: str, mapping: dict, records: list[dict] | None = None) -> dict:
    """Confirm the mapping and resolve it into the combined dataset.

    Returns ``{"mapped", "mapped_columns", "mapped_rows", "missing_required",
    "can_process"}`` where ``mapped`` is the combined DataFrame.
    """
    if backend_mode() == "api":
        body = _put(
            f"{api_base_url()}/api/sessions/{sid}/mapping", json={"mapping": mapping}
        ).json()
        return {
            "mapped": data_frame(sid, "mapped"),
            "mapped_columns": body.get("mapped_columns", []),
            "mapped_rows": body.get("mapped_rows", 0),
            "missing_required": body.get("missing_required", []),
            "can_process": body.get("can_process", False),
        }
    mapped = ingestion.apply_mapping(records or [], mapping)
    missing = ingestion.missing_required_columns(mapping)
    return {
        "mapped": mapped,
        "mapped_columns": list(mapped.columns),
        "mapped_rows": int(len(mapped)),
        "missing_required": missing,
        "can_process": not missing,
    }


def data_frame(sid: str, kind: str) -> pd.DataFrame:
    """Materialize a DataFrame from the backend: ``mapped`` | ``clean`` | ``flagged``."""
    if backend_mode() != "api":
        raise ReportServiceError("data_frame() is only available in API mode.")
    body = _get(f"{api_base_url()}/api/sessions/{sid}/data/{kind}").json()
    return _frame_from_columns_rows(body)


# --------------------------------------------------------------------------- #
# Processing (FR-CLN, FR-VAL)
# --------------------------------------------------------------------------- #
def run_process(sid: str, mapped_df: pd.DataFrame | None = None) -> dict:
    """Clean + validate. Returns log, counts, rules and the three DataFrames
    (cleaned, clean_subset, flagged) in both modes."""
    if backend_mode() == "api":
        body = _post(f"{api_base_url()}/api/sessions/{sid}/process").json()
        flagged = data_frame(sid, "flagged")
        clean_subset = data_frame(sid, "clean")
        cleaned = _reunite_cleaned(clean_subset, flagged)
        return {
            "log": body.get("log", {}),
            "counts": body.get("counts", {}),
            "rules": body.get("rules", {}),
            "cleaned": cleaned,
            "clean_subset": clean_subset,
            "flagged": flagged,
        }

    if mapped_df is None:
        raise ReportServiceError("A mapped DataFrame is required in local mode.")

    cleaned, log = cleaning.run_cleaning_pipeline(mapped_df.copy())
    masks = validation.validate_required_fields_by_column(cleaned, config.REQUIRED_COLUMNS)
    masks.update(
        validation.validate_types(cleaned, mapped_df, config.NUMERIC_COLUMNS, config.DATE_COLUMNS)
    )
    flagged = validation.build_review_table(cleaned, masks)
    clean_subset, flagged = validation.split_clean_and_flagged(cleaned, flagged)

    return {
        "log": log,
        "counts": {
            "rows_combined": int(len(mapped_df)),
            "duplicates_removed": int(log.get("duplicates_removed", 0)),
            "rows_flagged": int(len(flagged)),
            "clean_rows": int(len(clean_subset)),
        },
        "rules": {name: int(mask.sum()) for name, mask in masks.items()},
        "cleaned": cleaned,
        "clean_subset": clean_subset,
        "flagged": flagged,
    }


def _reunite_cleaned(clean_subset: pd.DataFrame, flagged: pd.DataFrame) -> pd.DataFrame:
    """Backend returns clean and flagged separately; rebuild the full cleaned
    frame (clean rows + flagged rows without the bookkeeping columns)."""
    if flagged is None or flagged.empty:
        return clean_subset.reset_index(drop=True) if clean_subset is not None else pd.DataFrame()
    if clean_subset is None or clean_subset.empty:
        cols = [c for c in flagged.columns if c not in ("_source_row", "_flag_reason")]
        return flagged[cols].reset_index(drop=True)
    return pd.concat(
        [
            clean_subset.reset_index(drop=True),
            flagged[list(clean_subset.columns)].reset_index(drop=True),
        ],
        ignore_index=True,
    )


# --------------------------------------------------------------------------- #
# Reporting (FR-OUT)
# --------------------------------------------------------------------------- #
def summary(
    sid: str,
    group_by: str,
    aggregate_column: str,
    aggregate_func: str,
    clean_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Grouped summary table (both modes return a DataFrame)."""
    if backend_mode() == "api":
        body = _get(
            f"{api_base_url()}/api/sessions/{sid}/report/summary",
            params={
                "group_by": group_by,
                "aggregate_column": aggregate_column,
                "aggregate_func": aggregate_func,
            },
        ).json()
        return _frame_from_columns_rows(body)
    if clean_df is None:
        raise ReportServiceError("A clean DataFrame is required in local mode.")
    return reporting.build_summary(clean_df, group_by, aggregate_column, aggregate_func)


# --------------------------------------------------------------------------- #
# Exports (FR-OUT-04/05/06)
# --------------------------------------------------------------------------- #
def export_bytes(
    sid: str,
    kind: str,
    fmt: str = "xlsx",
    frame: pd.DataFrame | None = None,
    group_by: str | None = None,
    aggregate_column: str | None = None,
    aggregate_func: str | None = None,
) -> bytes:
    """Downloadable bytes. In API mode the backend generates them; in local
    mode they are built from the provided frame (same output)."""
    fmt = (fmt or "xlsx").lower()
    if backend_mode() == "api":
        if kind == "bundle":
            return _get(f"{api_base_url()}/api/sessions/{sid}/export/bundle").content
        params = {"format": fmt}
        if kind == "summary":
            params.update(
                group_by=group_by or "region",
                aggregate_column=aggregate_column or "revenue",
                aggregate_func=aggregate_func or "sum",
            )
        return _get(f"{api_base_url()}/api/sessions/{sid}/export/{kind}", params=params).content

    frame = frame if frame is not None else pd.DataFrame()
    if kind in ("cleaned", "flagged"):
        if fmt == "csv":
            return core_export.to_csv_bytes(frame)
        return core_export.to_excel_bytes(frame, sheet_name="Clean data" if kind == "cleaned" else "Flagged rows")
    if kind == "summary":
        if fmt == "csv":
            return core_export.to_csv_bytes(frame)
        return core_export.to_excel_with_sheets({"Summary": frame, "Chart data": frame})
    raise ReportServiceError(f"Unknown export kind: {kind}")