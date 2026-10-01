"""Generate messy sample Excel/CSV files to exercise the full pipeline.

Run:  python sample_data/generate_sample_data.py
Outputs four files into sample_data/ with inconsistent column names, mixed
date/number formats, duplicates across files, and rows that should be
flagged (missing required fields, invalid dates, invalid amounts).
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
random.seed(42)

REGIONS = ["North", "South", "West"]
CUSTOMERS = [f"Customer {i:03d}" for i in range(1, 61)]


def _order_id(i: int) -> str:
    return f"ORD-{10000 + i}"


def _dates(start: date, days: int) -> list[date]:
    base = [start + timedelta(days=d) for d in range(days)]
    return base


def _base_rows(n: int, start: date) -> list[dict]:
    rows = []
    for i in range(n):
        row_date = _dates(start, n)[i]
        rows.append(
            {
                "order_id": _order_id(i),
                "date": row_date,
                "customer": random.choice(CUSTOMERS),
                "region": random.choice(REGIONS),
                "quantity": random.randint(1, 40),
                "revenue": round(random.uniform(40.0, 1500.0), 2),
            }
        )
    return rows


def main() -> None:
    start = date(2026, 9, 1)

    # 1) North region, messy header names, currency + thousand separators.
    north = _base_rows(50, start)
    for r in north:
        r["Revenue"] = f"${r.pop('revenue'):,.2f}"
        r["Qty."] = r.pop("quantity")
        r["Order Date"] = r.pop("date").strftime("%m/%d/%Y")
        r["Order ID"] = r.pop("order_id")
        r["Customer Name"] = r.pop("customer")
        r["Region"] = r.pop("region")
    # Two unreadable-format rows.
    north[3]["Order Date"] = "31/09/2026"          # invalid date
    north[7]["Order Date"] = ""                     # missing date
    pd.DataFrame(north).to_excel(HERE / "north-region-sales.xlsx", index=False)

    # 2) South region CSV: snake_case headers, European number formatting.
    south = _base_rows(45, start)
    for r in south:
        r["gross_sales"] = f"{r.pop('revenue'):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        r["quantity"] = r.pop("quantity")
        r["date_created"] = r.pop("date").isoformat()
        r["order_id"] = r.pop("order_id")
        r["Customer"] = r.pop("customer")
        r["Branch"] = r.pop("region")
    south[2]["gross_sales"] = "1.240,00"           # European decimal
    south[5]["gross_sales"] = "not available"       # invalid amount
    south[8]["order_id"] = ""                       # missing required field
    (HERE / "south-region-sales.csv").write_text(
        pd.DataFrame(south).to_csv(index=False), encoding="utf-8-sig"
    )

    # 3) West region, with a duplicate block copied from North (test dedupe).
    west = _base_rows(40, start)
    for r in west:
        r["Revenue"] = f"€ {r.pop('revenue'):,.2f}"  # euro symbol, comma thousands
        r["Qty"] = r.pop("quantity")
        r["Order Date"] = r.pop("date").strftime("%Y-%m-%d")
        r["Order ID"] = r.pop("order_id")
        r["Customer"] = r.pop("customer")
        r["Region"] = r.pop("region")
    west[4]["Order Date"] = "2026/09/12"            # alternative date format
    combined = pd.concat([pd.DataFrame(west), pd.DataFrame(west).iloc[:6]], ignore_index=True)
    combined.to_excel(HERE / "west-region-sales.xlsx", index=False)

    # 4) Online orders CSV: different names again + missing revenue row.
    online = _base_rows(60, start)
    for r in online:
        r["total_value"] = f"${r.pop('revenue'):,.2f}"
        r["buyer_name"] = r.pop("customer")
        r["date"] = r.pop("date").strftime("%d-%m-%Y")
        r["order_id"] = r.pop("order_id")
        r["region"] = r.pop("region")
    online[1]["total_value"] = ""                   # missing revenue
    online[6]["buyer_name"] = "  "                  # whitespace-only customer
    (HERE / "online-orders-sept.csv").write_text(
        pd.DataFrame(online).to_csv(index=False), encoding="utf-8-sig"
    )


if __name__ == "__main__":
    main()
    print("Sample files written to:", HERE)