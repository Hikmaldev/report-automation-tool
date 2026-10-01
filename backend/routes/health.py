"""Health check + session lifecycle endpoints (FR-SES-01/02)."""
from flask import Blueprint, jsonify

from ..errors import ApiError
from ..sessions import session_data, store

bp = Blueprint("health", __name__)


@bp.get("/api/health")
def health():
    """Liveness probe — does not require a session."""
    return jsonify(status="ok", service="Report Automation Tool API", version="1.0.0")


@bp.post("/api/sessions")
def create_session():
    sid = store().create()
    return jsonify({"session_id": sid, "state": snapshot(session_data(sid))}), 201


@bp.get("/api/sessions/<sid>")
def get_session(sid: str):
    return jsonify({"session_id": sid, "state": snapshot(session_data(sid))})


@bp.post("/api/sessions/<sid>/reset")
def reset_session(sid: str):
    """Discard all data but keep the id, so the client can start over."""
    try:
        store().reset(sid)
    except KeyError:
        raise ApiError(
            404, "Session not found or expired. Create a new one with POST /api/sessions."
        )
    return jsonify({"session_id": sid, "state": snapshot(session_data(sid))})


@bp.delete("/api/sessions/<sid>")
def delete_session(sid: str):
    if not store().delete(sid):
        raise ApiError(
            404, "Session not found or expired. Create a new one with POST /api/sessions."
        )
    return jsonify({"deleted": sid})


def snapshot(data: dict) -> dict:
    """Small JSON view of a session's state, used to drive a frontend step list."""
    files = [
        {"name": f["name"], "rows": f["rows"], "columns": f["columns"], "size_bytes": f["size_bytes"]}
        for f in data["files"]
    ]
    return {
        "files": files,
        "upload_errors": data["upload_errors"],
        "total_bytes": data["total_bytes"],
        "mapping_confirmed": bool(data["mapping"]),
        "missing_required": [],  # filled by the mapping endpoint
        "processed": data["processed"],
        "counts": {
            "files": len(files),
            "upload_rows": sum(f["rows"] for f in files),
            "mapped_rows": len(data["mapped"]) if data["mapped"] is not None else 0,
            "clean_rows": len(data["clean_subset"]) if data["clean_subset"] is not None else 0,
            "flagged_rows": len(data["flagged"]) if data["flagged"] is not None else 0,
        },
    }