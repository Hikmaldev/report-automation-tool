"""Smoke test: renders every page via Streamlit AppTest with realistic state."""
import io
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import cleaning, config, export, ingestion, validation

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = PROJECT_ROOT / "sample_data"
PAGES = {p: str(PROJECT_ROOT / "pages" / p) for p in (
    "overview.py", "upload.py", "column_mapping.py",
    "processing.py", "report.py", "review.py", "downloads.py",
)}


class UploadedFileLike(io.BytesIO):
    def __init__(self, path: Path):
        self.name = path.name
        self.size = path.stat().st_size
        super().__init__(path.read_bytes())


@pytest.fixture(scope="module")
def pipeline_state():
    paths = sorted(p for p in SAMPLE_DIR.glob("*.*") if p.suffix in (".xlsx", ".csv"))
    if not paths:
        pytest.skip("Run sample_data/generate_sample_data.py first.")
    records, errors = ingestion.read_multiple_files([UploadedFileLike(p) for p in paths])
    assert not errors

    mapping_frame = ingestion.build_mapping_frame(records)
    column_map = dict(zip(mapping_frame["source_column"], mapping_frame["standard_field"]))
    mapped = ingestion.apply_mapping(records, column_map)
    cleaned, log = cleaning.run_cleaning_pipeline(mapped)
    masks = validation.validate_required_fields_by_column(cleaned, config.REQUIRED_COLUMNS)
    masks.update(validation.validate_types(cleaned, mapped, config.NUMERIC_COLUMNS, config.DATE_COLUMNS))
    flagged = validation.build_review_table(cleaned, masks)
    clean_subset, flagged_out = validation.split_clean_and_flagged(cleaned, flagged)

    return {
        "records": records,
        "mapped": mapped,
        "cleaned": cleaned,
        "flags": log,
        "flagged": flagged_out,
        "clean": clean_subset,
    }


def _seed(at: AppTest, state: dict) -> None:
    for key, value in state.items():
        at.session_state[key] = value


def test_pages_without_state_render_cleanly():
    for page in PAGES.values():
        at = AppTest.from_file(page, default_timeout=30)
        at.run()
        assert not at.exception, f"{page}: {[e.value for e in at.exception]}"


def test_upload_page_with_records(pipeline_state):
    at = AppTest.from_file(PAGES["upload.py"], default_timeout=30)
    _seed(at, {"raw_dataframes": pipeline_state["records"], "file_errors": [], "removed_files": set()})
    at.run()
    assert not at.exception
    assert any("north" in str(t) for t in at.markdown) or any("north" in str(b) for b in at.button)


def test_column_mapping_page(pipeline_state):
    at = AppTest.from_file(PAGES["column_mapping.py"], default_timeout=30)
    _seed(at, {"raw_dataframes": pipeline_state["records"]})
    at.run()
    assert not at.exception


def test_processing_and_report_pages(pipeline_state):
    cases = [
        ("processing.py", {"mapped_df": pipeline_state["mapped"]}),
        ("report.py", {"mapped_df": pipeline_state["mapped"], "cleaned_df": pipeline_state["cleaned"]}),
        ("review.py", {"cleaned_df": pipeline_state["cleaned"]}),
        ("downloads.py", {"cleaned_df": pipeline_state["cleaned"]}),
    ]
    for page, extra in cases:
        at = AppTest.from_file(PAGES[page], default_timeout=30)
        _seed(at, extra)
        at.run()
        assert not at.exception, f"{page}: {[e.value for e in at.exception]}"


def test_full_results_pages(pipeline_state):
    st = pipeline_state
    processed = {
        "mapped_df": st["mapped"],
        "cleaned_df": st["cleaned"],
        "clean_df": st["clean"],
        "flagged_df": st["flagged"],
        "cleaning_log": st["flags"],
        "raw_dataframes": st["records"],
    }
    for page in ["processing.py", "report.py", "review.py", "downloads.py"]:
        at = AppTest.from_file(PAGES[page], default_timeout=30)
        _seed(at, processed)
        at.run()
        assert not at.exception, f"{page}: {[e.value for e in at.exception]}"


def test_overview_with_results(pipeline_state):
    at = AppTest.from_file(PAGES["overview.py"], default_timeout=30)
    _seed(
        at,
        {
            "raw_dataframes": pipeline_state["records"],
            "cleaned_df": pipeline_state["cleaned"],
            "flagged_df": pipeline_state["flagged"],
            "clean_df": pipeline_state["clean"],
            "cleaning_log": pipeline_state["flags"],
        },
    )
    at.run()
    assert not at.exception
    assert at.metric  # dashboard metrics rendered