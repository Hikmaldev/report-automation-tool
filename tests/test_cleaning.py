"""Unit tests for cleaning.py."""
import pandas as pd

from core import cleaning


def test_deduplicate_excludes_source_file():
    df = pd.DataFrame(
        {
            "order_id": ["A", "A", "B"],
            "date": ["2026-09-01", "2026-09-01", "2026-09-02"],
            "_source_file": ["f1.csv", "f2.csv", "f1.csv"],
        }
    )
    cleaned, removed = cleaning.deduplicate(df)
    assert removed == 1
    assert len(cleaned) == 2


def test_deduplicate_no_duplicates():
    df = pd.DataFrame({"a": [1, 2, 3]})
    cleaned, removed = cleaning.deduplicate(df)
    assert removed == 0
    assert len(cleaned) == 3


def test_standardize_numbers_us_and_european():
    col = pd.Series(["$1,240.00", "1.240,00", "12,5", "1,240", "€ 3.040,00", "not available", None])
    out = col.map(cleaning._to_float)
    assert out.iloc[0] == 1240.00
    assert out.iloc[1] == 1240.00
    assert out.iloc[2] == 12.5
    assert out.iloc[3] == 1240
    assert out.iloc[4] == 3040.00
    assert pd.isna(out.iloc[5])
    assert pd.isna(out.iloc[6])


def test_standardize_dates_to_iso():
    df = pd.DataFrame({"date": ["09/30/2026", "2026-09-30", "30-09-2026", "garbage"]})
    log = {}
    df = cleaning.standardize_dates(df, ["date"], log)
    assert df["date"].iloc[0] == "2026-09-30"
    assert df["date"].iloc[1] == "2026-09-30"
    assert df["date"].iloc[2] == "2026-09-30"
    assert pd.isna(df["date"].iloc[3])
    assert log["date_parse_failed"] >= 1


def test_standardize_text_trims_and_cases():
    df = pd.DataFrame({"customer": ["  Acme Inc ", "Beta  "], "region": ["north", "WEST "]})
    log = {}
    df = cleaning.standardize_text(df, ["customer", "region"], ["region"], log)
    assert df["customer"].iloc[0] == "Acme Inc"
    assert df["region"].tolist() == ["North", "West"]
    assert log.get("whitespace_trimmed", 0) >= 1


def test_cleaning_pipeline_notes_coerced_values():
    df = pd.DataFrame(
        {
            "order_id": ["1", "1", "2"],
            "date": ["2026-09-01", "2026-09-01", "bad-date"],
            "quantity": ["12", "12", "abc"],
            "revenue": ["$9.99", "$9.99", "—"],
            "customer": ["  Acme ", "  Acme ", "  Acme "],
            "region": ["north", "north", "north"],
        }
    )
    cleaned, log = cleaning.run_cleaning_pipeline(df)
    assert len(cleaned) == 2  # identical rows 0-1 collapse into one
    assert log["duplicates_removed"] == 1
    assert log["date_parse_failed"] >= 1
    assert log["number_parse_failed"] >= 1
    assert log["whitespace_trimmed"] >= 1