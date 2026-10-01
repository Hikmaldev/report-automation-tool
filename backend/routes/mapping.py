"""Column mapping endpoints (FR-CLN-06).

Mirrors the HTML/Streamlit mapping screen: the backend proposes a standard
field for every detected source column (from ``config.DEFAULT_COLUMN_MAP``),
the client confirms or corrects it, and the mapping is resolved to a combined
DataFrame before cleaning ever runs (Business rule 4).
"""
from flask import Blueprint, jsonify, request

from core import config, ingestion
from ..errors import ApiError
from ..serialization import records_from_df
from ..sessions import session_data

bp = Blueprint("mapping", __name__)

_ALLOWED_FIELDS = set(config.CANONICAL_FIELDS) | {config.IGNORE_LABEL}


def _snapshot_columns(data: dict) -> tuple[list[dict], dict]:
    frame = ingestion.build_mapping_frame(data["files"])
    rows = records_from_df(frame)
    confirmed = data["mapping"] or {
        row["source_column"]: row["standard_field"]
        for row in rows
        if row.get("standard_field")
    }
    missing = ingestion.missing_required_columns(confirmed)
    return rows, confirmed, missing


@bp.get("/api/sessions/<sid>/mapping")
def get_mapping(sid: str):
    data = session_data(sid)
    if not data["files"]:
        raise ApiError(409, "Upload at least one file before mapping columns.")
    rows, confirmed, missing = _snapshot_columns(data)
    return jsonify(
        {
            "columns": rows,
            "mapping": confirmed,
            "missing_required": missing,
            "can_process": not missing,
        }
    )


@bp.put("/api/sessions/<sid>/mapping")
def put_mapping(sid: str):
    data = session_data(sid)
    if not data["files"]:
        raise ApiError(409, "Upload at least one file before mapping columns.")

    body = request.get_json(silent=True) or {}
    mapping = body.get("mapping")
    if not isinstance(mapping, dict) or not mapping:
        raise ApiError(
            400,
            "Provide a non-empty 'mapping' object, e.g. "
            '{"mapping": {"Qty.": "quantity", "Revenue": "revenue"}}.',
        )

    normalized = {str(k): str(v) for k, v in mapping.items()}
    bad = sorted(set(normalized.values()) - _ALLOWED_FIELDS)
    if bad:
        raise ApiError(
            400,
            f"Unknown standard field(s): {', '.join(bad)}. "
            f"Use one of: {', '.join(sorted(_ALLOWED_FIELDS))}.",
        )

    data["mapping"] = normalized
    data["mapped"] = ingestion.apply_mapping(data["files"], normalized)
    data["cleaned"] = None
    data["flagged"] = None
    data["clean_subset"] = None
    data["cleaning_log"] = None
    data["processed"] = False

    missing = ingestion.missing_required_columns(normalized)
    return jsonify(
        {
            "applied": True,
            "mapping": normalized,
            "mapped_columns": list(data["mapped"].columns) if data["mapped"] is not None else [],
            "mapped_rows": len(data["mapped"]) if data["mapped"] is not None else 0,
            "missing_required": missing,
            "can_process": not missing,
        }
    )