"""Processing + review endpoints.

Runs the same pipeline as the Streamlit frontend: cleaning (dedupe, format
standardization) followed by validation, then splits rows into the clean
subset (used for reporting) and the flagged review table (FR-VAL-03/04/05).
"""
import pandas as pd
from flask import Blueprint, jsonify

from core import cleaning, config, validation
from ..errors import ApiError
from ..serialization import records_from_df
from ..sessions import session_data

bp = Blueprint("process", __name__)


@bp.post("/api/sessions/<sid>/process")
def run_process(sid: str):
    data = session_data(sid)
    if not data["files"]:
        raise ApiError(409, "Upload files first, then run the process.")
    if data["mapped"] is None:
        raise ApiError(
            409,
            "Column mapping must be confirmed before processing "
            "(PUT /api/sessions/<sid>/mapping).",
        )

    missing = _missing_required(data)
    if missing:
        raise ApiError(
            422,
            "Some required columns have no mapped source column, so the data "
            "cannot be processed yet.",
            details=missing,
        )

    mapped = data["mapped"]
    cleaned, log = cleaning.run_cleaning_pipeline(mapped.copy())

    masks = validation.validate_required_fields_by_column(cleaned, config.REQUIRED_COLUMNS)
    masks.update(
        validation.validate_types(cleaned, mapped, config.NUMERIC_COLUMNS, config.DATE_COLUMNS)
    )
    flagged = validation.build_review_table(cleaned, masks)
    clean_subset, flagged = validation.split_clean_and_flagged(cleaned, flagged)

    data.update(
        cleaned=cleaned,
        flagged=flagged,
        clean_subset=clean_subset,
        cleaning_log=log,
        processed=True,
    )

    return jsonify(
        {
            "log": log,
            "rules": {reason: int(mask.sum()) for reason, mask in masks.items()},
            "counts": {
                "rows_combined": int(len(mapped)),
                "duplicates_removed": int(log.get("duplicates_removed", 0)),
                "rows_flagged": int(len(flagged)),
                "clean_rows": int(len(clean_subset)),
            },
        }
    )


@bp.get("/api/sessions/<sid>/review")
def review_table(sid: str):
    """Flagged rows with their flag reasons (FR-VAL-03)."""
    data = session_data(sid)
    _require_processed(data)
    flagged = data["flagged"]
    if flagged is None:
        flagged = pd.DataFrame()
    return jsonify(
        {
            "columns": list(flagged.columns),
            "rows": records_from_df(flagged),
            "count": int(len(flagged)),
        }
    )


@bp.get("/api/sessions/<sid>/data/<kind>")
def data_slice(sid: str, kind: str):
    """Materialize a DataFrame as JSON for API-mode frontends.

    ``kind`` selects which frame: ``mapped`` (mapping confirmed), ``clean``
    (rows safe for reporting) or ``flagged`` (rows needing review).
    """
    data = session_data(sid)
    if kind == "mapped":
        if data["mapped"] is None:
            raise ApiError(409, "Confirm the column mapping first (PUT /api/sessions/<sid>/mapping).")
        frame = data["mapped"]
    elif kind == "clean":
        _require_processed(data)
        frame = data["clean_subset"] if data["clean_subset"] is not None else pd.DataFrame()
    elif kind == "flagged":
        _require_processed(data)
        frame = data["flagged"] if data["flagged"] is not None else pd.DataFrame()
    else:
        raise ApiError(400, "Unknown data kind. Use 'mapped', 'clean', or 'flagged'.")
    return jsonify(
        {
            "kind": kind,
            "columns": list(frame.columns),
            "rows": records_from_df(frame),
            "count": int(len(frame)),
        }
    )


def _missing_required(data: dict) -> list[str]:
    from core import ingestion

    return ingestion.missing_required_columns(data["mapping"])


def _require_processed(data: dict) -> None:
    if not data["processed"]:
        raise ApiError(409, "Process the data first (POST /api/sessions/<sid>/process).")