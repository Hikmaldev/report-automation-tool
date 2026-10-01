# Product Requirements Document (PRD)

## Excel/CSV Report Automation Tool

| Item             | Detail                               |
| ---------------- | ------------------------------------ |
| Document version | 1.0 (Draft)                          |
| Date             | October 1, 2026                      |
| Status           | Draft for review                     |
| Tech stack       | Python, Pandas, Streamlit (or Flask) |

---

## 1. Product Summary

The Excel/CSV Report Automation Tool is a small application that takes multiple raw Excel or CSV files, cleans the data, and produces a consolidated report as charts and downloadable tables. It replaces manual copy-paste reconciliation that currently takes hours and is prone to human error.

## 2. Background and Problem

Many internships and small back-office teams reconcile reports by hand. This usually means:

- Opening several Excel or CSV files one by one.
- Copying rows into one master sheet.
- Manually removing duplicate entries.
- Fixing inconsistent date, number, or text formats.
- Rebuilding charts every time new files arrive.
- Missing bad rows because nobody checks every cell.

This is slow and easy to get wrong. A single missed duplicate or a wrong date format can throw off the final numbers.

## 3. Goals and Success Metrics

### 3.1 Goals

1. Let a user upload several Excel or CSV files at once.
2. Clean the data automatically (duplicates, format inconsistencies).
3. Produce a consolidated summary as charts and tables.
4. Let the user download the cleaned output.
5. Flag rows that do not match the expected format, instead of silently dropping or guessing.

### 3.2 Success Metrics

| Metric                                  | Target                                        | How to measure                           |
| --------------------------------------- | --------------------------------------------- | ---------------------------------------- |
| Time to produce a consolidated report   | Under 5 minutes, versus hours manually        | Compare manual process time vs tool time |
| Duplicate rows remaining after cleaning | 0                                             | Manual spot check on sample files        |
| Rows flagged for manual review          | Visible and exportable                        | Count in the review table                |
| Files processed successfully in one run | At least 10 files, up to a defined size limit | Load test with sample files              |
| App load and processing time            | Under 10 seconds for files under 10 MB total  | Manual timing during testing             |

## 4. Scope

### 4.1 In Scope (MVP)

- Upload multiple Excel (.xlsx) and CSV files in one session.
- Detect and remove exact duplicate rows.
- Standardize common formats: dates, number formatting, text casing, trimming whitespace.
- Combine data from multiple files into one working dataset.
- Generate a summary view with at least one chart type (bar or line) and a summary table.
- Let the user download the cleaned dataset and the summary as Excel or CSV.
- Flag rows with missing required fields or invalid formats in a separate review table.

### 4.2 Out of Scope for MVP

- Scheduled or automatic recurring imports (e.g. watching a folder or inbox).
- Multi-user accounts, login, and permissions.
- Editing data directly inside the app.
- Connecting to external databases or APIs as a data source.
- Advanced statistical analysis beyond basic aggregation and charts.
- Support for file formats other than .xlsx and .csv.

## 5. Target Users

### 5.1 Persona

**Reporting Analyst / Intern (primary user)**

- Receives raw Excel or CSV exports from different sources or branches.
- Needs a clean, consolidated report quickly, often under a deadline.
- Is comfortable with Excel but not with writing code.
- Wants to see what went wrong, not just a silent "fixed" file.

**Supervisor / Reviewer (secondary user, read-only use)**

- Receives the final chart and table output.
- Does not use the tool directly, just consumes the exported report.

## 6. Functional Requirements

### 6.1 File Upload

| ID       | Requirement                                                                              | Priority |
| -------- | ---------------------------------------------------------------------------------------- | -------- |
| FR-UP-01 | User can upload multiple .xlsx and .csv files in a single session.                       | Must     |
| FR-UP-02 | System validates file extension and rejects unsupported formats with a clear message.    | Must     |
| FR-UP-03 | System shows a list of uploaded files with row counts before processing.                 | Must     |
| FR-UP-04 | System enforces a maximum file size and total upload size, configurable by the operator. | Should   |
| FR-UP-05 | User can remove a file from the upload list before running the process.                  | Should   |

### 6.2 Data Cleaning

| ID        | Requirement                                                                                                                                | Priority |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------ | -------- |
| FR-CLN-01 | System detects and removes exact duplicate rows across all uploaded files.                                                                 | Must     |
| FR-CLN-02 | System standardizes date formats to one consistent format (e.g. YYYY-MM-DD).                                                               | Must     |
| FR-CLN-03 | System standardizes number formats (decimal separator, thousand separator, currency symbols removed).                                      | Must     |
| FR-CLN-04 | System trims leading and trailing whitespace from text fields.                                                                             | Must     |
| FR-CLN-05 | System standardizes text casing for key columns (e.g. consistent capitalization) when configured.                                          | Should   |
| FR-CLN-06 | System lets the user map differently named columns from different files to one common column (e.g. "Qty" and "Quantity" become one field). | Should   |
| FR-CLN-07 | System logs every automatic change it makes, so cleaning is not a silent black box.                                                        | Should   |

### 6.3 Validation and Manual Review

| ID        | Requirement                                                                                                                   | Priority |
| --------- | ----------------------------------------------------------------------------------------------------------------------------- | -------- |
| FR-VAL-01 | System flags rows missing a required field.                                                                                   | Must     |
| FR-VAL-02 | System flags rows where a value does not match the expected data type (e.g. text in a numeric column).                        | Must     |
| FR-VAL-03 | System shows flagged rows in a separate review table, with the reason for flagging.                                           | Must     |
| FR-VAL-04 | User can download the flagged rows separately for manual correction.                                                          | Must     |
| FR-VAL-05 | Flagged rows are excluded from the summary charts and tables by default, with a visible count of how many rows were excluded. | Must     |

### 6.4 Report Output

| ID        | Requirement                                                                          | Priority |
| --------- | ------------------------------------------------------------------------------------ | -------- |
| FR-OUT-01 | System generates a summary table (e.g. totals grouped by category, branch, or date). | Must     |
| FR-OUT-02 | System generates at least one chart (bar or line) based on the summary table.        | Must     |
| FR-OUT-03 | User can choose which column to group by and which column to aggregate.              | Should   |
| FR-OUT-04 | User can download the cleaned combined dataset as .xlsx or .csv.                     | Must     |
| FR-OUT-05 | User can download the summary table and chart data as .xlsx.                         | Should   |
| FR-OUT-06 | User can download the flagged rows as a separate file.                               | Must     |

### 6.5 Session and State

| ID        | Requirement                                                                                                          | Priority |
| --------- | -------------------------------------------------------------------------------------------------------------------- | -------- |
| FR-SES-01 | The app keeps uploaded and processed data only for the current session. No data is stored permanently on the server. | Must     |
| FR-SES-02 | User can reset the session and start with new files without restarting the app.                                      | Should   |

## 7. Main User Flow

1. User opens the app.
2. User uploads several Excel or CSV files.
3. System shows the file list with row counts.
4. User clicks "Process."
5. System combines the files, removes duplicates, and standardizes formats.
6. System separates rows that fail validation into a review table.
7. System shows the summary table and chart based on the clean rows.
8. User downloads the cleaned dataset, the summary report, and the flagged rows.
9. If needed, user fixes the flagged rows outside the app and re-uploads them for another pass.

## 8. Non-Functional Requirements

### 8.1 Performance

- The app processes a combined dataset of up to 100,000 rows within about 10 seconds on typical hardware.
- The UI stays responsive while processing; the user sees a progress indicator for larger files.

### 8.2 Reliability

- The app does not crash on malformed files. It reports which file or row caused an error instead of stopping silently.
- Partial failures (one bad file among several good ones) do not block processing of the good files.

### 8.3 Usability

- No coding knowledge required to use the app.
- Clear, plain-language error and validation messages (no raw Python tracebacks shown to the user).
- The interface works on a standard laptop browser without extra setup beyond running the app.

### 8.4 Data Privacy

- No data leaves the local machine or the server the app runs on, unless the operator explicitly adds external storage later.
- Uploaded files are not logged or persisted beyond the active session.

### 8.5 Maintainability

- Cleaning and validation logic is written as small, testable Pandas functions, separate from the UI code.
- Configuration (required columns, file size limits, format rules) is kept in one place, not scattered across the code.

## 9. Technical Architecture

### 9.1 Stack

| Layer           | Technology                                         |
| --------------- | -------------------------------------------------- |
| Language        | Python 3.11+                                       |
| Data processing | Pandas                                             |
| UI              | Streamlit (default choice for MVP)                 |
| Alternative UI  | Flask, if a more customized web UI is needed later |
| File parsing    | openpyxl (xlsx), built-in csv / Pandas read_csv    |
| Charting        | Plotly or Matplotlib, rendered inside Streamlit    |

### 9.2 Component Overview

```
[User Browser]
      |
 [Streamlit App]
      |
  [Upload Handler] --> [File Parser: xlsx/csv]
      |
  [Cleaning Pipeline: dedupe, format standardization]
      |
  [Validation Engine: required fields, type checks]
      |-------------------------------------------|
[Clean Dataset]                        [Flagged Rows]
      |                                       |
[Summary + Chart Builder]              [Review Table UI]
      |
[Download Handler: xlsx/csv export]
```

### 9.3 Suggested Module Structure

| Module          | Responsibility                                                       |
| --------------- | -------------------------------------------------------------------- |
| `app.py`        | Streamlit entry point, page layout, user interaction                 |
| `ingestion.py`  | Reading and parsing uploaded xlsx/csv files into Pandas DataFrames   |
| `cleaning.py`   | Deduplication, format standardization functions                      |
| `validation.py` | Row-level checks, flagging logic, reason codes                       |
| `reporting.py`  | Grouping, aggregation, chart data preparation                        |
| `export.py`     | Building downloadable xlsx/csv files from DataFrames                 |
| `config.py`     | Required columns, size limits, format rules, column mapping defaults |

### 9.4 Core Business Rules

1. A row is a duplicate only if all mapped columns match exactly.
2. A row is flagged, not deleted, when it fails validation.
3. Flagged rows never appear in the summary charts unless the user explicitly includes them.
4. Column mapping is resolved before cleaning and validation run.
5. No file is modified on disk. All processing happens in memory for the session.

## 10. UI Requirements

### 10.1 Main Screens

| Screen            | Main Content                                                         |
| ----------------- | -------------------------------------------------------------------- |
| Upload            | File uploader, list of uploaded files with row counts, remove button |
| Column Mapping    | Table to match source columns to standard fields, shown when needed  |
| Processing Result | Summary of rows processed, duplicates removed, rows flagged          |
| Summary Report    | Grouping controls, summary table, chart                              |
| Review Table      | Flagged rows with reason, download button                            |
| Download Center   | Buttons for cleaned dataset, summary report, flagged rows            |

### 10.2 Design Principles

- Keep the flow linear: upload, review, download. Avoid hidden steps.
- Always show counts (files uploaded, duplicates removed, rows flagged) so the user trusts the process.
- Never silently discard data. Anything removed or changed is visible somewhere in the UI.

## 11. Release Plan

| Phase              | Scope                                                                 | Estimated Duration |
| ------------------ | --------------------------------------------------------------------- | ------------------ |
| Phase 0            | Requirements confirmation, sample file collection, module scaffolding | 1 week             |
| Phase 1 (MVP)      | Upload, cleaning, validation, basic summary and chart, downloads      | 2 to 3 weeks       |
| Phase 2            | Column mapping UI, configurable grouping/aggregation, cleaning log    | 1 to 2 weeks       |
| Phase 3 (optional) | Scheduled processing, folder watch, multi-user support                | To be scoped later |

## 12. Testing Strategy

- **Unit tests:** cleaning functions (dedupe, date/number standardization), validation rules.
- **Integration tests:** full pipeline from upload to export, using sample messy files.
- **Edge case tests:** empty files, files with only headers, files with mismatched columns, very large files.
- **Manual UAT:** a user with real messy Excel exports runs through the full flow.

## 13. Risks and Mitigation

| Risk                                                  | Impact                                             | Mitigation                                                                                 |
| ----------------------------------------------------- | -------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Source files have wildly inconsistent column names    | Cleaning pipeline fails or produces wrong results  | Column mapping step before cleaning; clear error when required columns are missing         |
| Large files slow down the Streamlit session           | Poor user experience                               | Enforce file size limits, show progress indicator, consider chunked reading                |
| Users expect the tool to fix everything automatically | Frustration when rows get flagged instead of fixed | Set expectations in the UI copy: flagged rows always need a human look                     |
| Sensitive business data uploaded to a shared server   | Privacy or compliance issue                        | Document that no data is persisted; consider local-only deployment for sensitive use cases |

## 14. Assumptions and Dependencies

**Assumptions**

- Input files are tabular with a header row. The tool is not meant for free-form or multi-sheet layouts with merged cells.
- A single person uses one session at a time. No concurrent multi-user editing is expected for MVP.

**Dependencies**

- Sample messy files are needed early to tune the cleaning and validation rules.
- If deployed for a team, hosting (local machine, internal server, or a simple cloud host) needs to be decided separately.

## 15. Future Enhancements (Backlog)

- Scheduled or folder-watch based automatic processing.
- Support for .xls (legacy Excel) and Google Sheets as a source.
- Multi-sheet Excel support with sheet selection.
- Saved cleaning templates per data source.
- Simple authentication if the tool is shared across a team.
- Export directly to Google Sheets or email the report automatically.

## 16. Open Questions

1. What are the most common column names and formats across the real source files this tool needs to handle first?
2. Is there a fixed set of required fields, or does it vary by report type?
3. Will this run locally per user, or does it need to be hosted for a team to share?
4. Is Streamlit's single-session model acceptable, or is multi-user access needed soon?

## 17. Glossary

| Term           | Meaning                                                                            |
| -------------- | ---------------------------------------------------------------------------------- |
| Dedupe         | Deduplication, the process of removing exact duplicate rows                        |
| Flagged row    | A row that failed validation and is set aside for manual review                    |
| Column mapping | Matching differently named source columns to one standard column name              |
| Session        | One continuous use of the app from upload to download, with no data kept afterward |
