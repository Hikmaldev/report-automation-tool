# 📊 Clearpath — Excel/CSV Report Automation Tool

![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-REST_API-000?logo=flask)
![Pandas](https://img.shields.io/badge/Pandas-2.x-150458?logo=pandas&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly-Charts-3F4F75?logo=plotly&logoColor=white)
![pytest](https://img.shields.io/badge/tests-pytest%2062%20%2B%20TestSprite%206-green)
![License](https://img.shields.io/badge/License-MIT-green)

**Clearpath** is a report automation tool that takes several raw Excel/CSV exports,
cleans them, flags anything questionable, and produces one consolidated report with
charts and downloadable artifacts. Built with **Streamlit** and a **Flask REST API**
that share a single framework-independent `core/` pipeline — no duplicated logic,
no data written to disk.

> *"Turn your raw exports into a report you can trust."*

---

## ✨ Key Features

### 🏠 Overview
- Landing dashboard with session metrics and quick actions

### 📤 Upload files
- Multi-file `.xlsx` / `.csv` upload with size limits (FR-UP-01…05)
- Per-file errors and remove buttons, live row & column counts

### 🔗 Column mapping
- Confirm how source columns map to standard fields before cleaning runs (FR-CLN-06)
- Missing required columns **block** processing with a clear message

### ⚙️ Processing
- Dedupe, date/number/text standardization, validation (FR-CLN-01…05, FR-VAL-01…05)
- Cleaning log and metric cards after every run

### 📈 Summary report
- Group-by / aggregate controls, Plotly bar/line chart, summary table (FR-OUT-01…03)
- Flagged rows are **excluded** from the summary — no silent data loss

### ⚠️ Review table
- Flagged rows with reasons, filter & search, scoped download (FR-VAL-03/04)

### 💾 Download center
- Cleaned dataset, summary report and flagged rows as `.xlsx` / `.csv` (FR-OUT-04…06)
- Everything generated in memory — nothing is stored on disk

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **UI** | [Streamlit](https://streamlit.io/) (`st.Page` + `st.navigation`) |
| **Language** | Python 3.10+ (3.11+ recommended) |
| **Core pipeline** | [pandas](https://pandas.pydata.org/) (cleaning, validation, reporting) |
| **Charts** | [Plotly](https://plotly.com/) |
| **REST API** | [Flask](https://flask.palletsprojects.com/) + Flask-CORS (reuses `core/` unchanged) |
| **Excel export** | [OpenPyXL](https://openpyxl.readthedocs.io/) (in-memory bytes) |
| **Tests** | pytest (core + API) · TestSprite (browser E2E) |

---

## 🗂️ Project Structure

```
Report-Automation-Tool/
├── app.py                  # entry point: st.Page + st.navigation
├── pages/                  # one script per screen of the user flow
├── core/                   # framework-independent pipeline modules
│   ├── config.py           # required columns, limits, mapping defaults (Design §4.6)
│   ├── ingestion.py        # file parsing, file-level errors, column mapping (§4.1)
│   ├── cleaning.py         # dedupe + format standardization, cleaning log (§4.2)
│   ├── validation.py       # required/type checks, review table, split (§4.3)
│   ├── reporting.py        # summary + chart data (§4.4)
│   ├── export.py           # in-memory xlsx/csv bytes (§4.5)
│   ├── service.py          # facade: pages call this; local pipeline or Flask API
│   └── ui.py               # session helpers shared by pages (§7)
├── backend/                # Flask REST API — same core, http layer only
│   ├── app.py              # create_app factory: blueprints, CORS, JSON error handlers
│   ├── wsgi.py             # run with: python -m backend.wsgi
│   ├── sessions.py         # in-memory per-session store (TTL, reset)
│   ├── uploadadapter.py    # Werkzeug FileStorage -> core's upload API
│   └── routes/             # health, upload, mapping, process, report, export
├── sample_data/            # generator for messy fixture files
├── tests/                  # pytest suite for core + API (§9)
├── testsprite-code/        # TestSprite browser E2E tests (Playwright)
└── testsprite-plans/       # original TestSprite plans (reference)
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+ (Python 3.11+ recommended by the PRD)

### 1. Clone & Install

```bash
git clone https://github.com/Hikmaldev/report-automation-tool.git
cd report-automation-tool
python -m venv .venv
.\.venv\Scripts\activate        # Windows
source .venv/bin/activate       # macOS / Linux

pip install -r requirements.txt
```

### 2. Generate Sample Data (Optional)

```bash
python sample_data/generate_sample_data.py
```

Creates messy `.csv` / `.xlsx` fixtures (duplicates, dirty dates, mixed currency)
so you can try the full flow right away.

### 3. Run the App

```bash
streamlit run app.py
```

Open the printed URL (default `http://localhost:8501`).

### 4. Run the Flask API (Optional)

```bash
# from the project root
.\.venv\Scripts\python.exe -m backend.wsgi        # http://localhost:5000
# or: flask --app backend.wsgi run --port 5000
```

---

## 🌐 Deploy to Streamlit Cloud

1. Push your code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → **Create app** → connect the repository
3. Set **Branch** = `main`, **Main file** = `app.py`
4. Open **Advanced settings** → pick Python **3.11/3.12** → click **Deploy** — done! 🎉

> **💡 No configuration needed!** Streamlit Cloud runs a single process, so the app
> serves in `local` mode automatically (sidebar shows **Backend: local**). No
> `REPORT_API_URL` or secrets required.

If you *also* host the Flask API (VPS/Render/Railway), point the app at it:

| Key | Value |
|---|---|
| `REPORT_API_URL` | e.g. `https://your-api.example.com` |
| `REPORT_API_MODE` | `api` or `local` — force a mode instead of auto-detecting |

---

## 📡 API Endpoints (Flask)

The same pipeline is exposed as a REST API for integrations or a custom frontend.
It reuses `core/` unchanged (PRD §9.3) with in-memory, per-session state (FR-SES-01/02).

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Liveness probe |
| `POST` | `/api/sessions` | Create a session → `{session_id}` |
| `GET` | `/api/sessions/<sid>` | Current state (files, counts, step flags) |
| `POST` | `/api/sessions/<sid>/reset` | Discard data, keep the id (FR-SES-02) |
| `DELETE` | `/api/sessions/<sid>` | Delete the session |
| `POST` | `/api/sessions/<sid>/files` | Multipart upload, field `files` (FR-UP-01…04) |
| `DELETE` | `/api/sessions/<sid>/files/<name>` | Remove one file (FR-UP-05) |
| `GET` | `/api/sessions/<sid>/mapping` | Detected columns + suggested standard fields (FR-CLN-06) |
| `PUT` | `/api/sessions/<sid>/mapping` | Confirm mapping `{"mapping": {...}}`; missing required columns are reported |
| `POST` | `/api/sessions/<sid>/process` | Cleaning + validation; returns log & counts (FR-CLN-07, FR-VAL-05) |
| `GET` | `/api/sessions/<sid>/review` | Flagged rows with reasons as JSON (FR-VAL-03) |
| `GET` | `/api/sessions/<sid>/data/<kind>` | Materialize a frame as JSON: `mapped` \| `clean` \| `flagged` |
| `GET` | `/api/sessions/<sid>/report/columns` | Group/aggregate choices for the UI (FR-OUT-03) |
| `GET` | `/api/sessions/<sid>/report/summary` | Summary table + chart data (FR-OUT-01/02) — `?group_by=&aggregate_column=&aggregate_func=` |
| `GET` | `/api/sessions/<sid>/export/cleaned` | Clean dataset xlsx\|csv (FR-OUT-04) — `?format=` |
| `GET` | `/api/sessions/<sid>/export/flagged` | Flagged rows xlsx\|csv (FR-VAL-04, FR-OUT-06) — `?format=` |
| `GET` | `/api/sessions/<sid>/export/summary` | Summary report xlsx\|csv (FR-OUT-05) — `?format=` + query params |
| `GET` | `/api/sessions/<sid>/export/bundle` | One workbook: Clean data, Summary, Flagged rows |

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

---

## 🏗️ Architecture

Every screen goes through **`core/service.py`** — pages never call the pipeline
modules directly. It has two interchangeable backends with an identical
interface, so the UI code does not know which one is active:

```
┌──────────────────────────────────────────────────────────────┐
│                  Streamlit frontend (app.py)                   │
│   pages/  (upload · mapping · processing · report · review)    │
│                      core/ui.py (session)                      │
└─────────────────────────────┬─────────────────────────────────┘
                              │ every page call goes through
                              ▼
                    core/service.py (facade)
              ┌──────────────────┴──────────────────┐
              ▼ local (default)                     ▼ api
     in-process core/ pipeline            Flask backend (backend/)
     ┌─────────────────────────┐    ┌───────────────────────────┐
     │ ingestion · cleaning    │    │ routes/ → core/service    │
     │ validation · reporting  │    │ sessions (in-memory, TTL) │
     │ export (bytes)          │    │ export bytes              │
     └─────────────────────────┘    └───────────────────────────┘
```

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

---

## 🧭 User Flow

1. **Overview** — landing dashboard with session metrics and quick actions
2. **Upload files** (FR-UP-01…05) — multi-file `.xlsx`/`.csv` upload, size limits,
   per-file errors, remove buttons, row counts
3. **Column mapping** (FR-CLN-06) — confirm how source columns map to standard
   fields before cleaning runs; missing required columns block processing
4. **Processing** (FR-CLN-01…05, FR-VAL-01…05) — dedupe, date/number/text
   standardization, validation, cleaning log, metrics
5. **Summary report** (FR-OUT-01…03) — group-by/aggregate controls, Plotly
   bar/line chart, summary table, flagged-row exclusion note
6. **Review table** (FR-VAL-03/04) — flagged rows with reasons, filter/search,
   scoped download
7. **Download center** (FR-OUT-04…06) — cleaned dataset, summary report and
   flagged rows as `.xlsx`/`.csv`, generated in memory

Nothing is stored: all data lives in `st.session_state` for the current session
(FR-SES-01) and can be cleared with the sidebar **Reset session** button (FR-SES-02).

---

## 🧪 Testing

### Unit & API — pytest

```bash
.\.venv\Scripts\python -m pytest tests -q
```

62 tests pass. The core modules contain no Streamlit or Flask imports, so they
can be unit-tested without any app running — and are reused as-is by both
frontends. `tests/test_api.py` drives the full backend flow through Flask's test
client (upload → mapping → process → review → summary → exports → reset).

### Browser End-to-End — TestSprite

Six browser tests run the real Streamlit app against a local instance through
the TestSprite CLI (sources in `testsprite-code/`, original plans in
`testsprite-plans/`):

```bash
# start the app, then (from the project root)
testsprite test run <test-id>... --local 8501
```

| Test | ID |
| --- | --- |
| Landing dashboard loads | `19d6cd24-2050-45c3-818c-a0e55a55c4f0` |
| Upload accepts a CSV and reports a broken file | `5606008e-5f01-4d15-85ec-af1f3366f0e0` |
| Full happy path: upload, map, process, summary | `3153a913-0d4e-423b-934a-a1f2f92069a9` |
| Mapping blocks processing when required columns are missing | `9ea3c290-44ef-4ae3-ab20-fd689147d8b7` |
| Review table shows flagged rows with reasons | `dfeb59cf-aa79-4fce-937f-78e77c07c68a` |
| Download center offers xlsx and csv for every artifact | `7faf0db6-d2be-4b39-8502-b8d19eb99d28` |

Project (TestSprite): `Report Automation Tool` (`4900cd2c-e001-40d1-9d8c-3a4e5c17cdb1`,
frontend, local :8501).

---

## 🔒 Data Safety

- **Nothing is written to disk** — sessions live in memory (FR-SES-01) and are
  discarded with the sidebar **Reset session** button (FR-SES-02)
- **No silent data loss** — flagged rows are excluded from the summary by
  default and always visible for review & re-download (FR-OUT-01, FR-VAL-03/04)
- **Plain-language errors** — the API returns JSON `error` messages and the UI
  shows readable messages, never raw tracebacks (PRD §8.3)
- **Framework-independent core** — `core/` imports neither Streamlit nor Flask,
  so the pipeline is reusable and deterministic across both frontends

---

## 📝 Notes

- Only `.xlsx` and `.csv` are supported (MVP scope)
- Multi-sheet Excel, scheduled imports and multi-user accounts are out of scope

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).

---

## 🤝 Contributing

Contributions are welcome! Feel free to open an *issue* or *pull request* for
bug fixes, new features, or documentation improvements.

1. Fork this repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add new feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

---

<p align="center">
  Built with ❤️ to turn messy exports into reports you can trust.
</p>