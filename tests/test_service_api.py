"""Service facade tests — API mode against a live Flask backend.

Boots the real Flask app on an ephemeral port and points the service at it
via ``REPORT_API_URL``, then runs the same user journey as the local-mode
tests to prove both backends expose an identical interface.
"""
import io
import threading
from pathlib import Path

import pandas as pd
import pytest
from werkzeug.serving import make_server

from backend.app import create_app
from core import service

SAMPLES = Path(__file__).resolve().parent.parent / "sample_data"


class FakeUpload(io.BytesIO):
    """Streamlit-style upload: bytes with .name and .size attributes."""

    def __init__(self, name: str, data: bytes):
        super().__init__(data)
        self.name = name
        self.size = len(data)


def _csv(name: str) -> FakeUpload:
    return FakeUpload(name, (SAMPLES / name).read_bytes())


def _files():
    return [_csv("online-orders-sept.csv"), _csv("south-region-sales.csv")]


@pytest.fixture(scope="module")
def api_url():
    app = create_app()
    server = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()


@pytest.fixture(autouse=True)
def _api_mode(monkeypatch, api_url):
    monkeypatch.setenv("REPORT_API_URL", api_url)
    monkeypatch.delenv("REPORT_API_MODE", raising=False)
    service.clear_cache()
    yield
    service.clear_cache()


def test_mode_detects_reachable_api(api_url):
    assert service.backend_mode() == "api"
    assert service.backend_info()["url"] == api_url


def test_full_flow_through_api(api_url):
    sid = service.new_session()
    records, errors = service.upload_files(sid, _files())
    assert errors == []
    assert len(records) == 2
    assert records[0]["df"] is None  # API mode: authoritative data lives on the backend

    mapping = dict(
        zip(
            service.mapping_frame(sid, records)["source_column"],
            service.mapping_frame(sid, records)["standard_field"],
        )
    )
    applied = service.apply_mapping(sid, mapping, records)
    assert applied["can_process"] is True
    assert applied["mapped"] is not None and not applied["mapped"].empty

    outcome = service.run_process(sid, applied["mapped"])
    assert outcome["counts"]["rows_combined"] == applied["mapped_rows"]
    assert outcome["counts"]["rows_flagged"] == len(outcome["flagged"])
    assert len(outcome["clean_subset"]) + len(outcome["flagged"]) == applied["mapped_rows"]
    assert "_flag_reason" in outcome["flagged"].columns

    summary = service.summary(sid, "region", "revenue", "sum", outcome["clean_subset"])
    assert not summary.empty
    assert summary["revenue"].sum() > 0

    csv_bytes = service.export_bytes(sid, "cleaned", "csv")
    assert b"order_id" in csv_bytes
    assert service.export_bytes(sid, "flagged", "xlsx").startswith(b"PK\x03\x04")
    assert service.export_bytes(
        sid, "summary", "xlsx", group_by="region", aggregate_column="revenue", aggregate_func="sum"
    ).startswith(b"PK\x03\x04")


def test_api_mode_matches_local_output(monkeypatch, api_url):
    """The same inputs must produce identical results in both backends."""
    files = _files()

    # --- local reference run ---
    monkeypatch.delenv("REPORT_API_URL")
    service.clear_cache()
    local_records, _ = service.upload_files(service.new_session(), files)
    local_mapping = dict(
        zip(
            service.mapping_frame(service.new_session(), local_records)["source_column"],
            service.mapping_frame(service.new_session(), local_records)["standard_field"],
        )
    )
    local_applied = service.apply_mapping(service.new_session(), local_mapping, local_records)
    local_out = service.run_process(service.new_session(), local_applied["mapped"])

    # --- api run ---
    monkeypatch.setenv("REPORT_API_URL", api_url)
    service.clear_cache()
    sid = service.new_session()
    records, _ = service.upload_files(sid, files)
    mapping = dict(
        zip(
            service.mapping_frame(sid, records)["source_column"],
            service.mapping_frame(sid, records)["standard_field"],
        )
    )
    applied = service.apply_mapping(sid, mapping, records)
    outcome = service.run_process(sid, applied["mapped"])

    assert applied["mapped_rows"] == local_applied["mapped_rows"]
    assert outcome["counts"] == local_out["counts"]

    # JSON round-trip turns NaN into None on the API path; normalize both sides.
    def _eq(api_df, local_df):
        return pd.testing.assert_frame_equal(
            api_df.mask(api_df.isna(), None).reset_index(drop=True),
            local_df.mask(local_df.isna(), None).reset_index(drop=True),
        )

    _eq(outcome["clean_subset"], local_out["clean_subset"])
    _eq(outcome["flagged"], local_out["flagged"])