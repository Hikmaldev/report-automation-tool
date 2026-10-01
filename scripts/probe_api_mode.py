"""Live probe: run the whole user journey through core.service in API mode
against the running Flask backend on localhost:5000 (no pytest involved)."""
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import service

SAMPLES = Path(__file__).resolve().parent.parent / "sample_data"


class FakeUpload(io.BytesIO):
    def __init__(self, name: str, data: bytes):
        super().__init__(data)
        self.name = name
        self.size = len(data)


def main() -> None:
    os.environ["REPORT_API_URL"] = "http://localhost:5000"
    service.clear_cache()
    print("mode:", service.backend_mode(), "| url:", service.backend_info()["url"])

    sid = service.new_session()
    files = [
        FakeUpload("online-orders-sept.csv", (SAMPLES / "online-orders-sept.csv").read_bytes()),
        FakeUpload("south-region-sales.csv", (SAMPLES / "south-region-sales.csv").read_bytes()),
    ]
    records, errors = service.upload_files(sid, files)
    print(f"upload: {len(records)} files accepted, {len(errors)} errors")
    total = sum(r["rows"] for r in records)
    print(f"rows billed by backend: {total}")

    frame = service.mapping_frame(sid, records)
    mapping = dict(zip(frame["source_column"], frame["standard_field"]))
    applied = service.apply_mapping(sid, mapping, records)
    print(f"mapping: {applied['mapped_rows']} combined rows, can_process={applied['can_process']}")

    outcome = service.run_process(sid, applied["mapped"])
    print(
        "process: combined=%s dup=%s flagged=%s clean=%s"
        % (
            outcome["counts"]["rows_combined"],
            outcome["counts"]["duplicates_removed"],
            outcome["counts"]["rows_flagged"],
            outcome["counts"]["clean_rows"],
        )
    )

    summary = service.summary(sid, "region", "revenue", "sum", outcome["clean_subset"])
    print("summary:")
    print(summary.to_string(index=False))

    csv_bytes = service.export_bytes(sid, "cleaned", "csv")
    xlsx_bytes = service.export_bytes(sid, "flagged", "xlsx")
    print(f"exports: cleaned.csv={len(csv_bytes)} bytes, flagged.xlsx={len(xlsx_bytes)} bytes")
    assert service.backend_mode() == "api"
    print("OK — API-mode journey complete")


if __name__ == "__main__":
    main()