"""Service facade tests — local mode (in-process pipeline).

Every page goes through ``core.service``; these tests pin the local backend so
the ``api`` integration tests can assert the two modes behave identically.
"""
import io
from pathlib import Path

import pytest

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


@pytest.fixture(autouse=True)
def _local_mode(monkeypatch):
    monkeypatch.delenv("REPORT_API_URL", raising=False)
    monkeypatch.delenv("REPORT_API_MODE", raising=False)
    service.clear_cache()
    yield
    service.clear_cache()


def _full_mapping(records) -> dict:
    frame = service.mapping_frame(service.new_session(), records)
    return dict(zip(frame["source_column"], frame["standard_field"]))


# --------------------------------------------------------------------------- #
# Mode resolution
# --------------------------------------------------------------------------- #
def test_default_mode_is_local():
    assert service.backend_mode() == "local"
    assert service.backend_info()["mode"] == "local"
    assert service.backend_info()["url"] is None


def test_forced_local_mode_ignores_api_url(monkeypatch):
    monkeypatch.setenv("REPORT_API_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("REPORT_API_MODE", "local")
    service.clear_cache()
    assert service.backend_mode() == "local"


def test_auto_mode_falls_back_when_api_unreachable(monkeypatch):
    monkeypatch.setenv("REPORT_API_URL", "http://127.0.0.1:1")  # nothing listens
    service.clear_cache()
    assert service.backend_mode() == "local"
    info = service.backend_info()
    assert info["error"] is not None  # probe failure recorded for the UI footer


# --------------------------------------------------------------------------- #
# Full user journey (local pipeline)
# --------------------------------------------------------------------------- #
def test_upload_mapping_process_report_export():
    sid = service.new_session()
    records, errors = service.upload_files(
        sid, [_csv("online-orders-sept.csv"), _csv("south-region-sales.csv")]
    )
    assert errors == []
    assert len(records) == 2
    assert all(r["df"] is not None and not r["df"].empty for r in records)

    mapping = dict(
        zip(
            service.mapping_frame(sid, records)["source_column"],
            service.mapping_frame(sid, records)["standard_field"],
        )
    )
    applied = service.apply_mapping(sid, mapping, records)
    assert applied["can_process"] is True
    assert applied["mapped_rows"] == len(applied["mapped"])
    assert applied["mapped_rows"] == len(records[0]["df"]) + len(records[1]["df"])

    outcome = service.run_process(sid, applied["mapped"])
    assert outcome["counts"]["rows_combined"] == applied["mapped_rows"]
    assert outcome["counts"]["rows_flagged"] == len(outcome["flagged"])
    assert outcome["counts"]["clean_rows"] == len(outcome["clean_subset"])
    # Nothing is silently dropped: clean + flagged == combined.
    assert len(outcome["clean_subset"]) + len(outcome["flagged"]) == applied["mapped_rows"]
    assert outcome["log"].get("duplicates_removed", 0) >= 0
    assert outcome["counts"]["rows_flagged"] >= 1  # sample data has blank order_ids
    assert "_flag_reason" in outcome["flagged"].columns

    summary = service.summary(sid, "region", "revenue", "sum", outcome["clean_subset"])
    assert not summary.empty
    assert summary.columns.tolist() == ["region", "revenue"]
    assert summary["revenue"].sum() > 0

    csv_bytes = service.export_bytes(sid, "cleaned", "csv", frame=outcome["clean_subset"])
    assert b"order_id" in csv_bytes
    xlsx_bytes = service.export_bytes(sid, "flagged", "xlsx", frame=outcome["flagged"])
    assert xlsx_bytes.startswith(b"PK\x03\x04")
    summary_xlsx = service.export_bytes(sid, "summary", "xlsx", frame=summary)
    assert summary_xlsx.startswith(b"PK\x03\x04")


def test_local_record_carries_dataframe():
    sid = service.new_session()
    records, _ = service.upload_files(sid, [_csv("online-orders-sept.csv")])
    assert records[0]["df"] is not None
    assert records[0]["rows"] == len(records[0]["df"])


def test_remove_file_is_noop_in_local_mode():
    sid = service.new_session()
    records, _ = service.upload_files(sid, [_csv("online-orders-sept.csv")])
    service.remove_file(sid, records[0]["name"])  # must not raise
    assert len(records) == 1


def test_data_frame_requires_api_mode():
    with pytest.raises(service.ReportServiceError):
        service.data_frame(service.new_session(), "clean")


def test_unknown_export_kind_is_clear_error():
    with pytest.raises(service.ReportServiceError):
        service.export_bytes(service.new_session(), "nope", "xlsx")