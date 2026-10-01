"""API tests for the Flask backend (tests/test_api.py).

Covers the whole flow from session creation to exports, mirroring the PRD
user journey: upload -> mapping -> process -> review -> summary -> downloads,
plus error handling (plain messages, no tracebacks, §8.3).
"""
import io

import pytest

from backend.app import create_app

MESSY_CSV = (
    "Order ID,Order Date,Customer Name,Region,Qty.,Revenue\n"
    'ORD-1,09/01/2026,Acme Inc,north,2,"$1,240.00"\n'
    'ORD-1,09/01/2026,Acme Inc,north,2,"$1,240.00"\n'
    'ORD-2,2026-09-02,Beta Co,south,"3","€ 3.040,00"\n'
    "ORD-3,31/09/2026,Gamma Ltd,north,four,not available\n"
)

MAPPING = {
    "Order ID": "order_id",
    "Order Date": "date",
    "Customer Name": "customer",
    "Region": "region",
    "Qty.": "quantity",
    "Revenue": "revenue",
}


@pytest.fixture
def client():
    app = create_app({"TESTING": True})
    return app.test_client()


@pytest.fixture
def sid(client):
    resp = client.post("/api/sessions")
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["session_id"]


def _csv_file(name="sales.csv", content=MESSY_CSV):
    return (io.BytesIO(content.encode("utf-8")), name)


def _upload(client, sid, *files):
    return client.post(
        f"/api/sessions/{sid}/files",
        data={"files": list(files)},
        content_type="multipart/form-data",
    )


def _confirm_mapping(client, sid, mapping=MAPPING):
    return client.put(f"/api/sessions/{sid}/mapping", json={"mapping": mapping})


def _run_full_flow(client, sid):
    """Upload one messy CSV, map every column, and process it."""
    assert _upload(client, sid, _csv_file()).status_code == 200
    assert _confirm_mapping(client, sid).get_json()["can_process"] is True
    return client.post(f"/api/sessions/{sid}/process")


# --------------------------------------------------------------------------- #
# Health + sessions
# --------------------------------------------------------------------------- #
def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_session_create_get_reset_delete(client, sid):
    assert client.get(f"/api/sessions/{sid}").status_code == 200

    resp = client.post(f"/api/sessions/{sid}/reset")
    assert resp.status_code == 200
    assert resp.get_json()["state"]["counts"]["files"] == 0

    assert client.delete(f"/api/sessions/{sid}").status_code == 200
    assert client.get(f"/api/sessions/{sid}").status_code == 404


def test_unknown_session_is_plain_404(client):
    resp = client.get("/api/sessions/does-not-exist")
    assert resp.status_code == 404
    assert "Session not found" in resp.get_json()["error"]
    assert "Traceback" not in resp.get_data(as_text=True)


# --------------------------------------------------------------------------- #
# Upload (FR-UP-01 … 05)
# --------------------------------------------------------------------------- #
def test_upload_reports_row_counts(client, sid):
    resp = _upload(client, sid, _csv_file())
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["counts"]["files"] == 1
    assert body["counts"]["rows"] == 4
    assert body["files"][0]["name"] == "sales.csv"


def test_upload_rejects_unsupported_extension_without_blocking(client, sid):
    resp = _upload(
        client,
        sid,
        _csv_file(name="notes.txt", content="not a table"),
        _csv_file(name="sales.csv"),
    )
    body = resp.get_json()
    assert body["counts"]["files"] == 1  # good file still accepted (§8.2)
    assert any("Unsupported" in e["message"] for e in body["errors"])


def test_upload_without_files_is_400(client, sid):
    resp = client.post(f"/api/sessions/{sid}/files", data={})
    assert resp.status_code == 400
    assert "No files provided" in resp.get_json()["error"]


def test_malformed_csv_is_reported_not_corrupted(client, sid):
    # An unquoted "$1,240.00" widens the data rows past the header. Some CSV
    # readers "succeed" with silently shifted columns; the pipeline must
    # reject the file with a per-file error instead (PRD §8.2).
    bad = (
        "Order ID,Order Date,Customer,Region,Qty,Revenue\n"
        "ORD-1,09/01/2026,Acme,north,2,$1,240.00\n"
    )
    resp = _upload(client, sid, _csv_file(name="bad.csv", content=bad))
    body = resp.get_json()
    assert body["counts"]["files"] == 0
    assert any("could not be read" in e["message"] for e in body["errors"])


def test_upload_enforces_session_total():
    # A fresh app with a tiny total limit: the whole-session warning shows up
    # without blocking the file (matches the Streamlit warning behavior).
    app = create_app({"TESTING": True, "MAX_TOTAL_UPLOAD_MB": 0.00001})
    client = app.test_client()
    sid = client.post("/api/sessions").get_json()["session_id"]

    resp = _upload(client, sid, _csv_file())
    body = resp.get_json()
    assert any("Total upload exceeds" in e["message"] for e in body["errors"])

    # Once the session is already at its limit, uploads are refused up front.
    app2 = create_app({"TESTING": True, "MAX_TOTAL_UPLOAD_MB": 0})
    client2 = app2.test_client()
    sid2 = client2.post("/api/sessions").get_json()["session_id"]
    resp = _upload(client2, sid2, _csv_file())
    assert resp.status_code == 400
    assert "total upload limit" in resp.get_json()["error"]


def test_remove_file_before_processing(client, sid):
    _upload(client, sid, _csv_file(name="a.csv"))
    resp = client.delete(f"/api/sessions/{sid}/files/a.csv")
    assert resp.status_code == 200
    assert resp.get_json()["files"] == []
    # Removing an unknown file is a JSON 404.
    resp = client.delete(f"/api/sessions/{sid}/files/ghost.csv")
    assert resp.status_code == 404
    assert "not in this session" in resp.get_json()["error"]


# --------------------------------------------------------------------------- #
# Mapping (FR-CLN-06, Business rule 4)
# --------------------------------------------------------------------------- #
def test_mapping_suggests_standard_fields(client, sid):
    _upload(client, sid, _csv_file())
    resp = client.get(f"/api/sessions/{sid}/mapping")
    body = resp.get_json()
    by_name = {c["source_column"]: c["standard_field"] for c in body["columns"]}
    assert by_name["Order ID"] == "order_id"
    assert by_name["Revenue"] == "revenue"
    assert by_name["Qty."] == "quantity"


def test_mapping_rejects_unknown_standard_field(client, sid):
    _upload(client, sid, _csv_file())
    resp = client.put(
        f"/api/sessions/{sid}/mapping", json={"mapping": {"Order ID": "bogus"}}
    )
    assert resp.status_code == 400
    assert "bogus" in resp.get_json()["error"]


def test_missing_required_blocks_processing(client, sid):
    _upload(client, sid, _csv_file())
    bad = dict(MAPPING, Revenue="ignore")
    resp = _confirm_mapping(client, sid, mapping=bad)
    assert resp.get_json()["missing_required"] == ["revenue"]

    resp = client.post(f"/api/sessions/{sid}/process")
    assert resp.status_code == 422
    assert resp.get_json()["details"] == ["revenue"]


# --------------------------------------------------------------------------- #
# Full pipeline
# --------------------------------------------------------------------------- #
def test_full_pipeline_counts_and_review(client, sid):
    resp = _run_full_flow(client, sid)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()

    # 4 raw rows, one exact duplicate -> 1 removed; ORD-3 fails validation.
    assert body["counts"]["duplicates_removed"] == 1
    assert body["counts"]["rows_flagged"] == 1
    assert body["counts"]["clean_rows"] == 2
    assert body["counts"]["rows_combined"] == 4

    # Cleaning log is visible (FR-CLN-07).
    assert body["log"]["duplicates_removed"] == 1
    assert body["log"]["date_parse_failed"] >= 1

    # Flagged row carries a human-readable reason (FR-VAL-03).
    review = client.get(f"/api/sessions/{sid}/review").get_json()
    assert review["count"] == 1
    reason = review["rows"][0]["_flag_reason"]
    assert "Invalid date" in reason and "Invalid amount" in reason


def test_processing_requires_upload_and_mapping(client, sid):
    assert client.post(f"/api/sessions/{sid}/process").status_code == 409
    _upload(client, sid, _csv_file())
    assert client.post(f"/api/sessions/{sid}/process").status_code == 409


def test_summary_defaults_and_custom_controls(client, sid):
    _run_full_flow(client, sid)

    resp = client.get(f"/api/sessions/{sid}/report/summary")
    body = resp.get_json()
    assert resp.status_code == 200
    assert len(body["rows"]) == 2  # north + south
    assert len(body["chart"]["labels"]) == 2

    # Group by customer instead.
    resp = client.get(
        f"/api/sessions/{sid}/report/summary?group_by=customer&aggregate_column=revenue&aggregate_func=sum"
    )
    assert resp.status_code == 200
    assert len(resp.get_json()["rows"]) == 2


def test_summary_bad_column_is_plain_400(client, sid):
    _run_full_flow(client, sid)
    resp = client.get(
        f"/api/sessions/{sid}/report/summary?group_by=does_not_exist"
    )
    assert resp.status_code == 400
    text = resp.get_data(as_text=True)
    assert "Traceback" not in text
    assert "not found" in resp.get_json()["error"]


def test_report_columns_lists_controls(client, sid):
    _run_full_flow(client, sid)
    body = client.get(f"/api/sessions/{sid}/report/columns").get_json()
    assert "region" in body["columns"]
    assert "revenue" in body["numeric_columns"]
    assert "Sum" in body["aggregate_functions"]


# --------------------------------------------------------------------------- #
# Exports (FR-OUT-04/05/06, FR-VAL-04)
# --------------------------------------------------------------------------- #
def test_export_cleaned_csv_excludes_flagged(client, sid):
    _run_full_flow(client, sid)
    resp = client.get(f"/api/sessions/{sid}/export/cleaned?format=csv")
    assert resp.status_code == 200
    assert resp.mimetype.startswith("text/csv")
    text = resp.get_data(as_text=True)
    assert "order_id" in text
    assert "ORD-2" in text
    assert "not available" not in text  # flagged row never exported as clean


def test_export_flagged_rows_separately(client, sid):
    _run_full_flow(client, sid)
    resp = client.get(f"/api/sessions/{sid}/export/flagged?format=csv")
    assert resp.status_code == 200
    assert "ORD-3" in resp.get_data(as_text=True)


def test_export_cleaned_xlsx_is_zip(client, sid):
    _run_full_flow(client, sid)
    resp = client.get(f"/api/sessions/{sid}/export/cleaned")
    assert resp.status_code == 200
    assert resp.get_data()[:2] == b"PK"
    assert "spreadsheetml" in resp.mimetype


def test_export_bundle_multisheet_xlsx(client, sid):
    _run_full_flow(client, sid)
    resp = client.get(f"/api/sessions/{sid}/export/bundle")
    assert resp.status_code == 200
    assert resp.get_data()[:2] == b"PK"
    assert resp.headers["Content-Disposition"].endswith("report_bundle.xlsx")


def test_export_summary_matches_query(client, sid):
    _run_full_flow(client, sid)
    resp = client.get(
        f"/api/sessions/{sid}/export/summary?format=csv&group_by=region&aggregate_column=revenue&aggregate_func=sum"
    )
    assert resp.status_code == 200
    assert resp.mimetype.startswith("text/csv")


def test_export_requires_processed_session(client, sid):
    _upload(client, sid, _csv_file())
    resp = client.get(f"/api/sessions/{sid}/export/cleaned")
    assert resp.status_code == 409
    assert "Process the data first" in resp.get_json()["error"]


# --------------------------------------------------------------------------- #
# Reset (FR-SES-02) and unknown routes
# --------------------------------------------------------------------------- #
def test_reset_clears_everything(client, sid):
    _run_full_flow(client, sid)
    client.post(f"/api/sessions/{sid}/reset")
    state = client.get(f"/api/sessions/{sid}").get_json()["state"]
    assert state["counts"]["files"] == 0
    assert state["counts"]["clean_rows"] == 0
    assert state["processed"] is False


def test_unknown_api_route_is_json_404(client):
    resp = client.get("/api/sessions/nope/nope/nope")
    assert resp.status_code == 404
    assert resp.is_json