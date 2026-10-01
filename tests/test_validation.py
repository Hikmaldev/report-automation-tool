"""Unit tests for validation.py and the end-to-end pipeline."""
import pandas as pd
import pytest

from core import cleaning, ingestion, reporting, validation


def test_validate_required_fields():
    df = pd.DataFrame({"order_id": ["1", "", None, "4"]})
    mask = validation.validate_required_fields(df, ["order_id"])
    assert mask.tolist() == [False, True, True, False]


def test_validate_types_only_flags_previously_nonempty():
    cleaned = pd.DataFrame({"revenue": [1200.0, None, None]})
    mapped = pd.DataFrame({"revenue": ["$1,200.00", "oops", None]})
    masks = validation.validate_types(cleaned, mapped, ["revenue"], [])
    assert "Invalid amount (revenue)" in masks
    assert masks["Invalid amount (revenue)"].tolist() == [False, True, False]


def test_build_review_table_multiple_reasons_per_row():
    df = pd.DataFrame(
        {
            "order_id": ["1", "2"],
            "date": ["2026-09-01", None],
            "revenue": [100.0, None],
        }
    )
    masks = {
        "Missing date": pd.Series([False, True], index=df.index),
        "Invalid revenue": pd.Series([True, False], index=df.index),
    }
    review = validation.build_review_table(df, masks)
    assert len(review) == 2
    reasons = review["_flag_reason"].tolist()
    assert reasons[0] == "Invalid revenue"
    assert reasons[1] == "Missing date"


def test_split_clean_and_flagged():
    df = pd.DataFrame({"a": [1, 2, 3, 4]})
    flagged = validation.build_review_table(
        df, {"bad": pd.Series([False, True, False, True], index=df.index)}
    )
    clean, flagged_out = validation.split_clean_and_flagged(df, flagged)
    assert clean["a"].tolist() == [1, 3]
    assert len(flagged_out) == 2


def test_full_pipeline_from_two_upload_shapes(messy_frame):
    mapped = messy_frame
    cleaned, log = cleaning.run_cleaning_pipeline(mapped)

    masks = validation.validate_required_fields_by_column(cleaned, ["order_id", "date", "customer", "region", "revenue"])
    masks.update(validation.validate_types(cleaned, mapped, ["quantity", "revenue"], ["date"]))
    flagged = validation.build_review_table(cleaned, masks)
    clean_subset, flagged_out = validation.split_clean_and_flagged(cleaned, flagged)

    # ORD-1 exists in two files with identical mapped values -> duplicate dropped.
    assert log["duplicates_removed"] >= 1
    # Rows with a bad date, bad amounts, or missing date must be flagged.
    assert len(flagged_out) >= 2
    assert "_source_row" in flagged_out.columns  # traceability kept
    assert clean_subset["date"].notna().all()

    summary = reporting.build_summary(clean_subset, "region", "revenue", "sum")
    assert set(summary.columns) == {"region", "revenue"}
    assert (summary["revenue"] >= 0).all()


def test_reporting_rejects_bad_columns(messy_frame):
    cleaned, _ = cleaning.run_cleaning_pipeline(messy_frame)
    with pytest.raises(ValueError):
        reporting.build_summary(cleaned, "not_a_column", "revenue", "sum")


def test_missing_required_blocked(messy_frame):
    mapping = {
        "Order ID": "order_id",
        # Order Date intentionally left unmapped -> date required field missing
        "Customer Name": "customer",
        "Region": "region",
        "Qty.": "quantity",
        "Revenue": "revenue",
    }
    missing = ingestion.missing_required_columns(mapping)
    assert "date" in missing