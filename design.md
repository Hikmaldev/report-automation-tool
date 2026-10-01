# Design Document

## Excel/CSV Report Automation Tool

| Item | Detail |
|---|---|
| Document version | 1.0 (Draft) |
| Date | October 1, 2026 |
| Companion document | PRD-Report-Automation-Tool.md |

---

## 1. Purpose

This document describes how the Excel/CSV Report Automation Tool is built: its architecture, data flow, module design, data model, and key technical decisions. It translates the PRD's functional requirements into a concrete implementation plan.

## 2. Goals of This Design

- Keep the pipeline simple: upload, clean, validate, report, export.
- Keep cleaning and validation logic separate from the UI, so it can be tested and reused.
- Make every automatic change visible to the user. No silent data loss.
- Support Streamlit for MVP, while keeping the core logic framework-independent so it can move to Flask later without a rewrite.

## 3. High-Level Architecture

```
                    +---------------------------+
                    |        Streamlit UI        |
                    |  (app.py, page sections)   |
                    +-------------+---------------+
                                  |
                                  v
                    +---------------------------+
                    |      Ingestion Layer       |
                    |      (ingestion.py)        |
                    +-------------+---------------+
                                  |
                                  v
                    +---------------------------+
                    |      Cleaning Pipeline     |
                    |       (cleaning.py)        |
                    +-------------+---------------+
                                  |
                                  v
                    +---------------------------+
                    |     Validation Engine      |
                    |      (validation.py)       |
                    +------+---------------+------+
                           |               |
                           v               v
                 +-----------------+  +------------------+
                 | Clean Dataset   |  |  Flagged Rows     |
                 +--------+--------+  +---------+---------+
                          |                     |
                          v                     v
                 +-----------------+  +------------------+
                 | Reporting Layer |  | Review Table UI   |
                 |  (reporting.py) |  +------------------+
                 +--------+--------+
                          |
                          v
                 +-----------------+
                 |  Export Layer   |
                 |  (export.py)    |
                 +-----------------+
```

Everything runs in a single process, in memory, for one user session. There is no database and no background job queue for the MVP.

## 4. Module Design

### 4.1 `ingestion.py`

**Responsibility:** turn uploaded files into clean, in-memory Pandas DataFrames, tagged with their source file name.

Key functions:

- `read_uploaded_file(file) -> pd.DataFrame`
  Detects extension (.xlsx vs .csv) and dispatches to the right reader. Adds a `_source_file` column so later steps and the review table can trace a row back to its origin file.

- `read_multiple_files(files: list) -> list[pd.DataFrame]`
  Calls `read_uploaded_file` for each file. Collects per-file errors (e.g. unreadable file, empty file) without stopping the whole batch. Returns both the successful DataFrames and a list of file-level errors.

- `combine_dataframes(dfs: list[pd.DataFrame], column_map: dict) -> pd.DataFrame`
  Applies column mapping (see 4.6) and concatenates all DataFrames into one working dataset.

**Design note:** file-level errors (a corrupt file, an unreadable sheet) are handled separately from row-level validation errors (handled in `validation.py`). This keeps "the file itself is broken" distinct from "this row inside a good file is bad."

### 4.2 `cleaning.py`

**Responsibility:** deterministic, rule-based cleaning that does not require human judgment.

Key functions:

- `deduplicate(df: pd.DataFrame, subset: list[str] | None) -> tuple[pd.DataFrame, int]`
  Drops exact duplicate rows based on the mapped columns. Returns the cleaned DataFrame and a count of rows removed, so the UI can report it.

- `standardize_dates(df: pd.DataFrame, date_columns: list[str]) -> pd.DataFrame`
  Parses each date column with `pd.to_datetime(errors="coerce")` and reformats to `YYYY-MM-DD`. Rows where parsing fails become `NaT`, which validation later flags as a format error rather than silently keeping a bad string.

- `standardize_numbers(df: pd.DataFrame, numeric_columns: list[str]) -> pd.DataFrame`
  Strips currency symbols and thousand separators, normalizes decimal separators, and casts to numeric. Uses `pd.to_numeric(errors="coerce")` so invalid values become `NaN` instead of crashing the pipeline.

- `standardize_text(df: pd.DataFrame, text_columns: list[str]) -> pd.DataFrame`
  Trims whitespace and applies consistent casing where configured.

- `run_cleaning_pipeline(df, config) -> tuple[pd.DataFrame, dict]`
  Runs the above in order and returns a cleaning log (a dict summarizing what changed: duplicates removed, values coerced to NaN, etc.) for FR-CLN-07.

**Design note:** cleaning never deletes a row because of a bad value. It converts bad values to missing (`NaN` / `NaT`). Deciding whether a missing value means "flag the row" is the validation engine's job, not the cleaning pipeline's. This keeps the two concerns separate and testable independently.

### 4.3 `validation.py`

**Responsibility:** decide which rows are trustworthy enough for the summary report, and record why a row is not.

Key functions:

- `validate_required_fields(df, required_columns) -> pd.Series`
  Returns a boolean mask of rows missing any required field.

- `validate_types(df, type_rules: dict) -> pd.Series`
  Returns a boolean mask of rows where a column's value could not be coerced to the expected type during cleaning (i.e. is `NaN`/`NaT` after cleaning but was not empty in the original input).

- `build_review_table(df, masks: dict[str, pd.Series]) -> pd.DataFrame`
  Combines all failure masks into one flagged-rows DataFrame with a `_flag_reason` column listing every rule the row failed (a row can fail more than one rule).

- `split_clean_and_flagged(df, review_table) -> tuple[pd.DataFrame, pd.DataFrame]`
  Returns the subset of rows with no flags (used for reporting) and the flagged subset (shown in the review table).

**Design note:** `_flag_reason` is a list, not a single value, because a row can be missing a required field and have a bad date at the same time. The review table should show all reasons, not just the first one found.

### 4.4 `reporting.py`

**Responsibility:** turn the clean dataset into a summary table and chart-ready data.

Key functions:

- `build_summary(df, group_by: str, aggregate_column: str, aggregate_func: str) -> pd.DataFrame`
  Wraps `df.groupby(group_by)[aggregate_column].agg(aggregate_func)`.

- `build_chart_data(summary_df) -> dict`
  Prepares the structure Plotly/Matplotlib needs (labels and values) from the summary table.

**Design note:** this module only reads the clean dataset. It never sees flagged rows unless the user explicitly opts in, matching FR-VAL-05.

### 4.5 `export.py`

**Responsibility:** turn DataFrames back into downloadable files.

Key functions:

- `to_excel_bytes(df: pd.DataFrame) -> bytes`
  Uses `openpyxl` via `pd.ExcelWriter` writing to an in-memory buffer (`io.BytesIO`), so nothing touches disk.

- `to_csv_bytes(df: pd.DataFrame) -> bytes`

- `build_download_bundle(clean_df, summary_df, flagged_df) -> dict[str, bytes]`
  Produces all three downloadable artifacts in one call for the Download Center screen.

### 4.6 `config.py`

**Responsibility:** single source of truth for rules that would otherwise be scattered through the code.

Contains:

- `REQUIRED_COLUMNS`: list of columns that must be present and non-empty.
- `DATE_COLUMNS`, `NUMERIC_COLUMNS`, `TEXT_COLUMNS`: which cleaning rule applies to which column.
- `DEFAULT_COLUMN_MAP`: default mapping of known column name variants (e.g. `"Qty"`, `"qty"`, `"Quantity"` all map to `quantity`) to reduce manual mapping in FR-CLN-06.
- `MAX_FILE_SIZE_MB`, `MAX_TOTAL_UPLOAD_MB`: enforced in the ingestion layer per FR-UP-04.

**Design note:** keeping this in one file means adding support for a new report type is mostly a config change, not a code change across five modules.

## 5. Data Flow (Step by Step)

1. User uploads files through the Streamlit file uploader widget (`st.file_uploader`, `accept_multiple_files=True`).
2. `ingestion.read_multiple_files` parses each file into a DataFrame, tagging rows with `_source_file`.
3. If the user has non-standard column names, the Column Mapping screen lets them confirm or adjust the mapping before continuing. `DEFAULT_COLUMN_MAP` pre-fills this where possible.
4. `ingestion.combine_dataframes` merges everything into one working DataFrame.
5. `cleaning.run_cleaning_pipeline` runs deduplication and format standardization, producing a cleaning log.
6. `validation.build_review_table` and `validation.split_clean_and_flagged` separate the dataset into clean rows and flagged rows.
7. `reporting.build_summary` and `reporting.build_chart_data` run on the clean subset only.
8. The UI renders: processing summary counts, the chart, the summary table, and the review table.
9. `export.build_download_bundle` prepares the three downloadable files, offered through `st.download_button`.

## 6. Data Model (In-Memory)

There is no persistent database. The relevant "tables" are all in-memory Pandas DataFrames during a session:

| DataFrame | Description | Key columns |
|---|---|---|
| `raw_df` | Combined, unmapped data straight from ingestion | original source columns, `_source_file` |
| `mapped_df` | After column mapping is applied | standardized column names, `_source_file` |
| `cleaned_df` | After deduplication and format standardization | standardized column names, cleaned values |
| `flagged_df` | Rows that failed validation | all cleaned columns plus `_flag_reason` |
| `clean_subset_df` | Rows with no flags, used for reporting | same as `cleaned_df` minus flagged rows |
| `summary_df` | Grouped and aggregated result | `group_by` column, aggregated value column |

## 7. UI Structure (Streamlit)

Streamlit apps are organized as a linear script with conditional sections, driven by `st.session_state` to remember progress across reruns.

Suggested session state keys:

- `session_state.raw_dataframes`
- `session_state.column_map`
- `session_state.cleaned_df`
- `session_state.flagged_df`
- `session_state.summary_config` (group-by column, aggregate column, aggregate function)

Suggested page sections (single-page app with expanders or tabs, not separate routes, to keep MVP simple):

1. **Upload** — `st.file_uploader`, file list with row counts, remove button.
2. **Column Mapping** — editable table (`st.data_editor`) shown only if mapping is ambiguous.
3. **Processing Summary** — metrics via `st.metric`: files processed, duplicates removed, rows flagged.
4. **Summary Report** — controls (`st.selectbox`) for group-by and aggregate column/function, followed by chart and table.
5. **Review Table** — `st.dataframe` of flagged rows with `_flag_reason`, plus a download button scoped to just this table.
6. **Download Center** — three `st.download_button` widgets for cleaned data, summary report, and flagged rows.

## 8. Error Handling Strategy

| Situation | Handling |
|---|---|
| Unsupported file type uploaded | Rejected at ingestion with a plain-language message; other files still process |
| Corrupt or unreadable file | Caught per-file, reported in a file-level error list, does not stop the batch |
| Missing required column across all files | Stops processing with a clear message naming the missing column, before cleaning runs |
| Value that cannot be parsed as date/number | Converted to `NaN`/`NaT` in cleaning, caught and flagged in validation, never silently kept as-is |
| Empty file (headers only, no rows) | Treated as zero rows, included in file list with a 0 row count, not an error |
| User uploads the same file twice | Not treated specially; if rows are identical, deduplication naturally merges them |

No raw Python tracebacks are shown to the end user. Internally, the app logs exceptions with enough context (file name, step) for debugging, separate from what the UI displays.

## 9. Testing Approach

| Test type | What it covers | Tooling |
|---|---|---|
| Unit tests | `cleaning.py` and `validation.py` functions against small, crafted DataFrames | `pytest` |
| Integration tests | Full pipeline from a folder of sample messy files to final export bytes | `pytest`, sample fixture files |
| Edge case tests | Empty file, header-only file, all-duplicate file, mismatched columns, oversized file | `pytest` with fixture files per case |
| Manual UAT | Full Streamlit flow with real (anonymized) messy exports | Manual walkthrough |

Testable core logic lives outside Streamlit (`ingestion.py`, `cleaning.py`, `validation.py`, `reporting.py`, `export.py`), so most of it can be unit tested without spinning up the Streamlit app itself.

## 10. Key Technical Decisions

| Decision | Reasoning |
|---|---|
| Streamlit over Flask for MVP | Faster to build a working UI with file upload, tables, and charts; matches a solo-developer timeline |
| In-memory processing, no database | MVP doesn't need persistence across sessions; keeps privacy simple (nothing stored) |
| Cleaning converts bad values to NaN instead of deleting rows | Keeps row-level decisions (delete vs flag) in one place: validation, not scattered across cleaning functions |
| Config-driven required columns and format rules | Adapting to a new report type becomes a config change, not a rewrite |
| Column mapping step before cleaning | Prevents cleaning functions from silently operating on the wrong column when source files use different names |
| No raw error messages shown to user | Keeps the tool approachable for non-technical users, per PRD usability requirement |

## 11. Migration Path to Flask (If Needed Later)

Because `ingestion.py`, `cleaning.py`, `validation.py`, `reporting.py`, and `export.py` contain no Streamlit-specific code, a future move to Flask would mean:

1. Replace `app.py` with Flask routes and HTML templates (or a separate frontend).
2. Replace `st.session_state` with Flask session handling or a lightweight per-request state pattern.
3. Replace `st.file_uploader` / `st.download_button` with Flask's request file handling and `send_file`.
4. Reuse every function in the five core modules unchanged.

## 12. Open Design Questions

1. Should the cleaning log (FR-CLN-07) be shown in the UI, exported as a file, or both?
2. Should column mapping be remembered between sessions (e.g. saved to a local config file), or re-entered every time for MVP?
3. What is a reasonable default for `MAX_FILE_SIZE_MB` given the real files this tool will handle first?
4. Should flagged rows support a "fix inline and re-include" action in a later phase, or only export-and-reupload as in MVP?
