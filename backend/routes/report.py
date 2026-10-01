"""Reporting endpoints (FR-OUT-01/02/03).

Summary is always built from the clean subset — flagged rows are excluded by
default per FR-VAL-05. ``reporting.build_summary`` raises ValueError for bad
user choices and the app-level handler turns that into a plain 400 message.
"""
from flask import Blueprint, jsonify, request

from core import config, reporting
from ..errors import ApiError
from ..serialization import records_from_df
from ..sessions import session_data

bp = Blueprint("report", __name__)

_DEFAULT_GROUP = "region"
_DEFAULT_AGG = "revenue"


def _normalize_func(value: str) -> str:
    if value in config.AGGREGATE_FUNCTIONS:  # accept label "Sum" or value "sum"
        return config.AGGREGATE_FUNCTIONS[value]
    return value


@bp.get("/api/sessions/<sid>/report/columns")
def report_columns(sid: str):
    """Columns available for grouping/aggregation + valid functions."""
    data = session_data(sid)
    _require_processed(data)
    columns = list(data["clean_subset"].columns)
    return jsonify(
        {
            "columns": columns,
            "numeric_columns": [c for c in config.NUMERIC_COLUMNS if c in columns],
            "date_columns": [c for c in config.DATE_COLUMNS if c in columns],
            "aggregate_functions": config.AGGREGATE_FUNCTIONS,
        }
    )


@bp.get("/api/sessions/<sid>/report/summary")
def report_summary(sid: str):
    data = session_data(sid)
    _require_processed(data)

    group_by = request.args.get("group_by", _DEFAULT_GROUP)
    aggregate_column = request.args.get("aggregate_column", _DEFAULT_AGG)
    aggregate_func = _normalize_func(request.args.get("aggregate_func", "sum"))

    summary = reporting.build_summary(
        data["clean_subset"], group_by, aggregate_column, aggregate_func
    )

    chart = (
        {
            "labels": summary[group_by].tolist(),
            "values": summary[aggregate_column].tolist(),
        }
        if not summary.empty
        else {"labels": [], "values": []}
    )

    return jsonify(
        {
            "group_by": group_by,
            "aggregate_column": aggregate_column,
            "aggregate_func": aggregate_func,
            "columns": list(summary.columns),
            "rows": records_from_df(summary),
            "chart": chart,
        }
    )


def _require_processed(data: dict) -> None:
    if not data["processed"]:
        raise ApiError(409, "Process the data first (POST /api/sessions/<sid>/process).")