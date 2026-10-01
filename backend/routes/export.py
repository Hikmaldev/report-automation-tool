"""Download endpoints (FR-OUT-04/05/06, FR-VAL-04).

All files are generated in memory from DataFrames via ``core.export`` and
streamed with Flask's ``send_file`` — nothing touches disk (Business rule 5).
"""
from io import BytesIO

import pandas as pd
from flask import Blueprint, jsonify, request, send_file

from core import config, export as core_export, reporting
from ..errors import ApiError
from ..sessions import session_data

bp = Blueprint("export", __name__)

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
CSV_MIME = "text/csv; charset=utf-8"


def _require_processed(data: dict) -> None:
    if not data["processed"]:
        raise ApiError(409, "Process the data first (POST /api/sessions/<sid>/process).")


def _send_frame(df: pd.DataFrame, fmt: str, stem: str):
    fmt = (fmt or "xlsx").lower()
    if fmt == "csv":
        return send_file(
            BytesIO(core_export.to_csv_bytes(df)),
            mimetype=CSV_MIME,
            as_attachment=True,
            download_name=f"{stem}.csv",
        )
    if fmt == "xlsx":
        return send_file(
            BytesIO(core_export.to_excel_bytes(df)),
            mimetype=XLSX_MIME,
            as_attachment=True,
            download_name=f"{stem}.xlsx",
        )
    raise ApiError(400, "Unsupported export format. Use 'xlsx' or 'csv'.")


def _build_summary(data: dict) -> pd.DataFrame:
    group_by = request.args.get("group_by", "region")
    aggregate_column = request.args.get("aggregate_column", "revenue")
    func = request.args.get("aggregate_func", "sum")
    if func in config.AGGREGATE_FUNCTIONS:
        func = config.AGGREGATE_FUNCTIONS[func]
    return reporting.build_summary(data["clean_subset"], group_by, aggregate_column, func)


@bp.get("/api/sessions/<sid>/export/cleaned")
def export_cleaned(sid: str):
    data = session_data(sid)
    _require_processed(data)
    frame = data["clean_subset"] if data["clean_subset"] is not None else pd.DataFrame()
    return _send_frame(frame, request.args.get("format", "xlsx"), "cleaned_data")


@bp.get("/api/sessions/<sid>/export/flagged")
def export_flagged(sid: str):
    data = session_data(sid)
    _require_processed(data)
    frame = data["flagged"] if data["flagged"] is not None else pd.DataFrame()
    return _send_frame(frame, request.args.get("format", "xlsx"), "flagged_rows")


@bp.get("/api/sessions/<sid>/export/summary")
def export_summary(sid: str):
    data = session_data(sid)
    _require_processed(data)
    summary = _build_summary(data)
    return _send_frame(summary, request.args.get("format", "xlsx"), "summary_report")


@bp.get("/api/sessions/<sid>/export/bundle")
def export_bundle(sid: str):
    """One workbook with Clean data, Summary and Flagged rows (Download center)."""
    data = session_data(sid)
    _require_processed(data)
    summary = _build_summary(data)
    sheets = {
        "Clean data": data["clean_subset"] if data["clean_subset"] is not None else pd.DataFrame(),
        "Summary": summary,
        "Flagged rows": data["flagged"] if data["flagged"] is not None else pd.DataFrame(),
    }
    body = core_export.to_excel_with_sheets(sheets)
    return send_file(
        BytesIO(body),
        mimetype=XLSX_MIME,
        as_attachment=True,
        download_name="report_bundle.xlsx",
    )


@bp.get("/api/sessions/<sid>/export/meta")
def export_meta(sid: str):
    """Small JSON cheat-sheet of the available download endpoints."""
    data = session_data(sid)
    _require_processed(data)
    return jsonify(
        {
            "cleaned": "/api/sessions/<sid>/export/cleaned?format=xlsx|csv",
            "flagged": "/api/sessions/<sid>/export/flagged?format=xlsx|csv",
            "summary": "/api/sessions/<sid>/export/summary?format=xlsx|csv&group_by=region&aggregate_column=revenue&aggregate_func=sum",
            "bundle": "/api/sessions/<sid>/export/bundle (xlsx, multiple sheets)",
        }
    )