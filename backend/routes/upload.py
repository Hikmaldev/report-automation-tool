"""File upload endpoints (FR-UP-01 … FR-UP-05).

Multipart upload with the form field name ``files``. Per-file failures are
reported in the response instead of blocking the whole batch (PRD §8.2):
a bad file among good ones never stops the good ones.
"""
from flask import Blueprint, current_app, jsonify, request

from core import ingestion
from ..errors import ApiError
from ..sessions import session_data
from ..uploadadapter import UploadedFileAdapter

bp = Blueprint("upload", __name__)


def _invalidate_outputs(data: dict) -> None:
    """Files changed: anything derived from them is no longer valid."""
    data["mapped"] = None
    data["cleaned"] = None
    data["flagged"] = None
    data["clean_subset"] = None
    data["cleaning_log"] = None
    data["processed"] = False


@bp.post("/api/sessions/<sid>/files")
def upload_files(sid: str):
    data = session_data(sid)
    files = request.files.getlist("files")
    if not files:
        raise ApiError(
            400,
            "No files provided. Send one or more files with the form field name 'files'.",
        )

    # Werkzeug's FileStorage uses .name for the form field; the core pipeline
    # expects .name to be the file name (Streamlit API), so adapt each file.
    adapters = [
        UploadedFileAdapter(f) for f in files if f.filename
    ]
    if not adapters:
        raise ApiError(400, "No files were actually selected for upload.")

    max_file_mb = current_app.config["MAX_FILE_SIZE_MB"]
    remaining_bytes = current_app.config["MAX_TOTAL_UPLOAD_MB"] * 1_000_000 - data[
        "total_bytes"
    ]
    if remaining_bytes <= 0:
        raise ApiError(
            400,
            "This session's total upload limit is already reached. "
            "Remove files or reset the session to upload more.",
        )

    records, errors = ingestion.read_multiple_files(
        adapters,
        max_file_size_mb=max_file_mb,
        max_total_mb=remaining_bytes / 1_000_000,
    )

    data["files"].extend(records)
    data["upload_errors"].extend(errors)
    data["total_bytes"] += sum(r["size_bytes"] for r in records)
    _invalidate_outputs(data)

    accepted = [
        {"name": r["name"], "rows": r["rows"], "columns": r["columns"], "size_bytes": r["size_bytes"]}
        for r in records
    ]
    return jsonify(
        {
            "files": accepted,
            "errors": errors,
            "counts": {
                "files": len(data["files"]),
                "rows": sum(f["rows"] for f in data["files"]),
                "total_bytes": data["total_bytes"],
            },
        }
    )


@bp.delete("/api/sessions/<sid>/files/<path:filename>")
def remove_file(sid: str, filename: str):
    """Remove one uploaded file before processing (FR-UP-05)."""
    data = session_data(sid)
    before = len(data["files"])
    data["files"] = [f for f in data["files"] if f["name"] != filename]
    if len(data["files"]) == before:
        raise ApiError(404, f"File '{filename}' is not in this session's upload list.")
    data["total_bytes"] = sum(f["size_bytes"] for f in data["files"])
    _invalidate_outputs(data)
    return jsonify(
        {"removed": filename, "files": [f["name"] for f in data["files"]]}
    )