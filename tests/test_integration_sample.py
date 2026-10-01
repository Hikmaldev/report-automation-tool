"""Integration tests: full pipeline on the generated sample files (Design §9).

Skips cleanly when sample_data fixtures have not been generated yet.
"""
import io
from pathlib import Path

import pytest

from core import cleaning, config, export, ingestion, reporting, validation

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"


class UploadedFileLike(io.BytesIO):
    """Mimics Streamlit's UploadedFile: a seekable buffer with name/size."""

    def __init__(self, path: Path):
        self.name = path.name
        self.size = path.stat().st_size
        super().__init__(path.read_bytes())


@pytest.fixture
def sample_uploads():
    paths = sorted(p for p in SAMPLE_DIR.glob("*.*") if p.suffix in (".xlsx", ".csv"))
    if not paths:
        pytest.skip("Run sample_data/generate_sample_data.py first.")
    return [UploadedFileLike(p) for p in paths]


def test_batch_parses_every_file_and_reports_clean(sample_uploads):
    records, errors = ingestion.read_multiple_files(sample_uploads)
    assert len(records) == len(sample_uploads)
    assert errors == []


def test_e2e_pipeline_on_sample_data(sample_uploads):
    records, errors = ingestion.read_multiple_files(sample_uploads)
    assert not errors

    mapping_frame = ingestion.build_mapping_frame(records)
    column_map = dict(zip(mapping_frame["source_column"], mapping_frame["standard_field"]))
    assert ingestion.missing_required_columns(column_map) == []

    mapped = ingestion.apply_mapping(records, column_map)
    assert len(mapped) > 0

    cleaned, log = cleaning.run_cleaning_pipeline(mapped)
    # west-region-sales.xlsx contains 6 duplicated rows by construction.
    assert log["duplicates_removed"] >= 6
    assert log["dates"] > 0
    assert log["date_parse_failed"] >= 1  # injected invalid date '31/09/2026'
    assert (cleaned["revenue"].dropna() >= 0).all()

    masks = validation.validate_required_fields_by_column(cleaned, config.REQUIRED_COLUMNS)
    masks.update(validation.validate_types(cleaned, mapped, config.NUMERIC_COLUMNS, config.DATE_COLUMNS))
    flagged = validation.build_review_table(cleaned, masks)
    clean_subset, flagged_out = validation.split_clean_and_flagged(cleaned, flagged)

    # The generator deliberately injects problematic rows.
    assert 1 <= len(flagged_out) <= 20
    assert all("Missing required field" in r or "Invalid" in r for r in flagged_out["_flag_reason"])

    summary = reporting.build_summary(clean_subset, "region", "revenue", "sum")
    assert not summary.empty
    assert list(summary.columns) == ["region", "revenue"]

    bundle = export.build_download_bundle(clean_subset, summary, flagged_out)
    assert {"cleaned_xlsx", "cleaned_csv", "summary_xlsx", "flagged_xlsx", "flagged_csv"} <= set(bundle)
    for name, content in bundle.items():
        assert isinstance(content, bytes) and len(content) > 0


def test_e2e_rejects_unsupported_extension(sample_uploads):
    bad = UploadedFileLike(Path(SAMPLE_DIR, "..", "README.md"))
    records, errors = ingestion.read_multiple_files([bad])
    assert records == []
    assert errors and "Unsupported file type" in errors[0]["message"]