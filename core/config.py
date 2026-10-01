"""Single source of truth for report rules (Design doc §4.6).

Adding support for a new report type should be mostly a change in this file,
not a rewrite across the pipeline modules.
"""

# ---------------------------------------------------------------------------
# Canonical schema
# ---------------------------------------------------------------------------
# The common, standardized columns the pipeline is expected to produce.
CANONICAL_FIELDS = ["order_id", "date", "customer", "region", "quantity", "revenue"]

# Columns that must be present AND non-empty for a row to be trustworthy.
REQUIRED_COLUMNS = ["order_id", "date", "customer", "region", "revenue"]

# Which cleaning rule applies to which column.
DATE_COLUMNS = ["date"]
NUMERIC_COLUMNS = ["quantity", "revenue"]
TEXT_COLUMNS = ["customer", "region"]
# Text columns whose casing is standardized when configured (FR-CLN-05).
CASING_COLUMNS = ["region"]

# ---------------------------------------------------------------------------
# Column mapping defaults (FR-CLN-06)
# ---------------------------------------------------------------------------
# Known source-column name variants -> canonical field. Lookup happens on a
# normalized name (lowercased, whitespace collapsed).
DEFAULT_COLUMN_MAP = {
    # order id
    "order id": "order_id",
    "order_id": "order_id",
    "orderid": "order_id",
    "order no": "order_id",
    "order number": "order_id",
    "ord_id": "order_id",
    "id": "order_id",
    # date
    "date": "date",
    "order date": "date",
    "orderdate": "date",
    "created at": "date",
    "created_at": "date",
    "date_created": "date",
    "tanggal": "date",
    # customer
    "customer": "customer",
    "customer name": "customer",
    "customername": "customer",
    "buyer": "customer",
    "buyer name": "customer",
    "buyer_name": "customer",
    "client": "customer",
    "client name": "customer",
    "pelanggan": "customer",
    # region
    "region": "region",
    "branch": "region",
    "area": "region",
    "cabang": "region",
    "wilayah": "region",
    # quantity
    "quantity": "quantity",
    "qty": "quantity",
    "qty.": "quantity",
    "units": "quantity",
    "jumlah": "quantity",
    "unit": "quantity",
    # revenue
    "revenue": "revenue",
    "sales": "revenue",
    "amount": "revenue",
    "total": "revenue",
    "total value": "revenue",
    "total_value": "revenue",
    "gross sales": "revenue",
    "gross_sales": "revenue",
    "net sales": "revenue",
    "price": "revenue",
    "pendapatan": "revenue",
}

# Label shown in the mapping screener for the "ignore this column" option.
IGNORE_LABEL = "ignore"

# ---------------------------------------------------------------------------
# Upload limits (FR-UP-04)
# ---------------------------------------------------------------------------
MAX_FILE_SIZE_MB = 10
MAX_TOTAL_UPLOAD_MB = 50

SUPPORTED_EXTENSIONS = {".xlsx", ".csv"}

# Column added during ingestion so rows can be traced back to their origin file.
NORMALIZED_HEADER = "_source_file"

# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
AGGREGATE_FUNCTIONS = {
    "Sum": "sum",
    "Average": "mean",
    "Count": "count",
    "Minimum": "min",
    "Maximum": "max",
}