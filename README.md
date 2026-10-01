# Clearpath — Excel/CSV Report Automation Tool

A small Streamlit app that takes several raw Excel/CSV exports, cleans them,
flags anything questionable, and produces a consolidated report with charts
and downloadable artifacts. Built from `PRD-Report-Automation-Tool.md` and
`design.md`.

## Quick start

```bash
# 1) create a virtual environment and install dependencies
python -m venv .venv
.\.venv\Scripts\activate        # Windows
source .venv/bin/activate       # macOS / Linux

pip install -r requirements.txt

# 2) (optional) generate messy sample files to try the full flow
python sample_data/generate_sample_data.py

# 3) run the app
streamlit run app.py
```

Open the printed URL (default `http://localhost:8501`).

## Backend API (Flask)

The same pipeline is exposed as a REST API for integrations or a custom
frontend. It reuses `core/` unchanged (PRD §9.3) with in-memory, per-session
state (FR-SES-01/02). No data is ever written to disk.

```bash
# from the project root
.\.venv\Scripts\python.exe -m backend.wsgi        # http://localhost:5000
# or: flask --app backend.wsgi run --port 5000
```

### Endpoint map

| Method & path | Purpose |
| --- | --- |
| `GET /api/health` | Liveness probe |
| `POST /api/sessions` | Create a session → `{session_id}` |
| `GET /api/sessions/<sid>` | Current state (files, counts, step flags) |
| `POST /api/sessions/<sid>/reset` | Discard data, keep the id (FR-SES-02) |
| `DELETE /api/sessions/<sid>` | Delete the session |
| `POST /api/sessions/<sid>/files` | Multipart upload, field `files` (FR-UP-01…04) |
| `DELETE /api/sessions/<sid>/files/<name>` | Remove one file (FR-UP-05) |
| `GET /api/sessions/<sid>/mapping` | Detected columns + suggested standard fields (FR-CLN-06) |
| `PUT /api/sessions/<sid>/mapping` | Confirm mapping `{"mapping": {...}}`; missing required columns are reported |
| `POST /api/sessions/<sid>/process` | Cleaning + validation; returns log & counts (FR-CLN-07, FR-VAL-05) |
| `GET /api/sessions/<sid>/review` | Flagged rows with reasons as JSON (FR-VAL-03) |
| `GET /api/sessions/<sid>/data/<kind>` | Materialize a frame as JSON: `mapped` \| `clean` \| `flagged` (for API-mode frontends) |
| `GET /api/sessions/<sid>/report/columns` | Group/aggregate choices for the UI (FR-OUT-03) |
| `GET /api/sessions/<sid>/report/summary?group_by=&aggregate_column=&aggregate_func=` | Summary table + chart data (FR-OUT-01/02) |
| `GET /api/sessions/<sid>/export/cleaned?format=xlsx\|csv` | Clean dataset (FR-OUT-04) |
| `GET /api/sessions/<sid>/export/flagged?format=xlsx\|csv` | Flagged rows (FR-VAL-04, FR-OUT-06) |
| `GET /api/sessions/<sid>/export/summary?format=xlsx\|csv&…` | Summary report (FR-OUT-05) |
| `GET /api/sessions/<sid>/export/bundle` | One workbook: Clean data, Summary, Flagged rows |

Every error is returned as JSON with a plain-language `error` message — never
a raw traceback (PRD §8.3). Example client calls:

```bash
curl -s -X POST http://localhost:5000/api/sessions
curl -s -X POST http://localhost:5000/api/sessions/<sid>/files \
     -F "files=@sample_data/south-region-sales.csv"
curl -s -X PUT http://localhost:5000/api/sessions/<sid>/mapping \
     -H "Content-Type: application/json" \
     -d '{"mapping": {"Qty.": "quantity", "Revenue": "revenue"}}'
curl -s -X POST http://localhost:5000/api/sessions/<sid>/process
curl -s -o cleaned.xlsx "http://localhost:5000/api/sessions/<sid>/export/cleaned"
```

## Frontend ↔ Backend (service layer)

Every screen goes through `core/service.py` — pages never call the pipeline
modules directly. It has two interchangeable backends with an identical
interface, so the UI code does not know which one is active:

| Mode | When | What happens |
| --- | --- | --- |
| `local` (default) | `REPORT_API_URL` is unset, or the API is unreachable | the in-process `core/` pipeline runs inside the Streamlit process |
| `api` | `REPORT_API_URL` is set and `/api/health` answers | every page call (upload, mapping, process, summary, export) is delegated to the Flask backend over HTTP |

```bash
# optional: point the app at the Flask backend (falls back to local automatically)
export REPORT_API_URL="http://localhost:5000"   # macOS / Linux
$env:REPORT_API_URL = "http://localhost:5000"   # Windows PowerShell

# optional: force a mode instead of auto-detecting
export REPORT_API_MODE=api    # or: local
```

Deploying on Streamlit Cloud? Do nothing — the app runs in `local` mode there
(Cloud runs a single process), and the Flask layer stays an optional
integration for VPS/Render/Railway hosts.

## User flow (maps to the PRD)

1. **Overview** — landing dashboard with session metrics and quick actions.
2. **Upload files** (FR-UP-01…05) — multi-file `.xlsx`/`.csv` upload, size
   limits, per-file errors, remove buttons, row counts.
3. **Column mapping** (FR-CLN-06) — confirm how source columns map to
   standard fields before cleaning runs; missing required columns block
   processing with a clear message.
4. **Processing** (FR-CLN-01…05, FR-VAL-01…05) — dedupe, date/number/text
   standardization, validation, cleaning log, metrics.
5. **Summary report** (FR-OUT-01…03) — group-by/aggregate controls, Plotly
   bar/line chart, summary table, flagged-row exclusion note.
6. **Review table** (FR-VAL-03/04) — flagged rows with reasons, filter/search,
   scoped download.
7. **Download center** (FR-OUT-04…06) — cleaned dataset, summary report and
   flagged rows as `.xlsx`/`.csv`, generated in memory.

Nothing is stored: all data lives in `st.session_state` for the current
session (FR-SES-01) and can be cleared with the sidebar **Reset session**
button (FR-SES-02).

## Project structure

```
app.py                  # entry point: st.Page + st.navigation
pages/                  # one script per screen of the user flow
core/                   # framework-independent pipeline modules
├── config.py           # required columns, limits, mapping defaults (Design §4.6)
├── ingestion.py        # file parsing, file-level errors, column mapping (§4.1)
├── cleaning.py         # dedupe + format standardization, cleaning log (§4.2)
├── validation.py       # required/type checks, review table, split (§4.3)
├── reporting.py        # summary + chart data (§4.4)
├── export.py           # in-memory xlsx/csv bytes (§4.5)
├── service.py          # facade: pages call this; local pipeline or Flask API (REPORT_API_URL)
└── ui.py               # session helpers shared by pages (§7)
backend/                # Flask REST API — same core, http layer only
├── app.py              # create_app factory: blueprints, CORS, JSON error handlers
├── wsgi.py             # run with: python -m backend.wsgi
├── sessions.py         # in-memory per-session store (TTL, reset)
├── uploadadapter.py    # Werkzeug FileStorage -> core's upload API
└── routes/             # health, upload, mapping, process, report, export
sample_data/            # generator for messy fixture files
tests/                  # pytest suite for core + API (§9)
```

## Testing

```bash
.\.venv\Scripts\python -m pytest tests -q
```

The core modules contain no Streamlit or Flask imports, so they can be
unit-tested without any app running — and are reused as-is by both frontends.
`tests/test_api.py` drives the full backend flow through Flask's test client
(upload → mapping → process → review → summary → exports → reset).

## Notes

- Python 3.10+ (Python 3.11+ recommended by the PRD).
- Only `.xlsx` and `.csv` are supported (MVP scope). Multi-sheet Excel,
  scheduled imports and multi-user accounts are out of scope.