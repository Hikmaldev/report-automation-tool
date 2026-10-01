"""Shared pytest fixtures: a small, deliberately messy dataset."""
from pathlib import Path

import pandas as pd
import pytest

from core import cleaning, config, ingestion, validation


@pytest.fixture
def messy_frame() -> pd.DataFrame:
    """Combine two fake uploads with different column names into a mapped frame."""
    north = pd.DataFrame(
        {
            "Order ID": ["ORD-1", "ORD-2", "ORD-3", "ORD-4"],
            "Order Date": ["09/01/2026", "2026-09-02", "31/09/2026", ""],
            "Customer Name": ["Acme Inc", "  Beta Co ", "Gamma Ltd", "Delta"],
            "Region": ["north", "south", "north", "west"],
            "Qty.": [2, "3", "four", 5],
            "Revenue": ["$1,240.00", "€ 3.040,00", "not available", "$500"],
            "_source_file": ["north.xlsx"] * 4,
        }
    )
    south = pd.DataFrame(
        {
            "order_id": ["ORD-1", "ORD-3"],
            "date": ["09/01/2026", "2026-09-01"],  # ORD-1 mirrors north exactly -> duplicate
            "customer": ["Acme Inc", "Gamma Ltd"],
            "branch": ["north", "north"],
            "quantity": [2, "four"],
            "gross_sales": ["$1,240.00", "not available"],
            "_source_file": ["south.csv"] * 2,
        }
    )
    records = [
        {"name": "north.xlsx", "df": north, "rows": len(north)},
        {"name": "south.csv", "df": south, "rows": len(south)},
    ]
    mapping = {
        "Order ID": "order_id",
        "Order Date": "date",
        "Customer Name": "customer",
        "Region": "region",
        "Qty.": "quantity",
        "Revenue": "revenue",
        "order_id": "order_id",
        "date": "date",
        "customer": "customer",
        "branch": "region",
        "quantity": "quantity",
        "gross_sales": "revenue",
    }
    return ingestion.apply_mapping(records, mapping)


@pytest.fixture
def mapped_clean(messy_frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(mapped_df, cleaned_df) after running the cleaning pipeline."""
    cleaned, _ = cleaning.run_cleaning_pipeline(messy_frame)
    return messy_frame, cleaned


@pytest.fixture
def sample_files_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "sample_data"