"""Step 1 — Upload files (FR-UP-01 … FR-UP-05)."""
import streamlit as st

from core import config, ingestion, theme, ui

ui.init_state()
theme.render_theme()
theme.render_sidebar("upload")

theme.page_header(
    "Step 01 · Ingestion",
    "Bring your files together",
    "Upload your Excel or CSV exports and we'll prepare them for a clean, "
    f"consolidated report. Up to {config.MAX_FILE_SIZE_MB} MB per file, "
    f"{config.MAX_TOTAL_UPLOAD_MB} MB total, .xlsx and .csv only.",
)

uploaded = st.file_uploader(
    "Choose your Excel or CSV exports",
    type=["xlsx", "csv"],
    accept_multiple_files=True,
    help="You can select several files at once.",
)

if uploaded:
    records, errors = ingestion.read_multiple_files(uploaded)
    existing = {r["name"]: r for r in st.session_state[ui.K_RAW]}
    removed = st.session_state[ui.K_REMOVED]
    for rec in records:
        if rec["name"] not in removed and rec["name"] not in existing:
            existing[rec["name"]] = rec
    st.session_state[ui.K_RAW] = list(existing.values())
    if errors:
        st.session_state[ui.K_FILE_ERRORS] = errors

# File-level errors (FR-UP-02, FR-UP-04) — plain language, never a traceback.
for err in st.session_state[ui.K_FILE_ERRORS]:
    st.error(f"**{err['file']}** — {err['message']}")

files = st.session_state[ui.K_RAW]


def remove_file(name: str) -> None:
    st.session_state[ui.K_REMOVED].add(name)
    st.session_state[ui.K_RAW] = [r for r in st.session_state[ui.K_RAW] if r["name"] != name]


if files:
    st.subheader("Files ready to process")
    for rec in files:
        left, mid, right = st.columns([5, 2, 1], vertical_alignment="center")
        left.markdown(f"**{rec['name']}**  \n{rec['rows']:,} rows · {rec['size_bytes'] / 1_000_000:.1f} MB")
        mid.caption(f"{len(rec['columns'])} columns")
        right.button("✕", key=f"remove_{rec['name']}", help="Remove this file", on_click=remove_file, args=(rec["name"],))

    total_rows = sum(r["rows"] for r in files)
    total_mb = sum(r["size_bytes"] for r in files) / 1_000_000
    st.caption(f"**{len(files)} file(s), {total_rows:,} rows, {total_mb:.1f} MB** ready.")

    st.divider()
    back, forward = st.columns([1, 3])
    if back.button("← Overview"):
        st.switch_page("pages/overview.py")
    if forward.button("Continue to column mapping →", type="primary", width="stretch"):
        st.switch_page("pages/column_mapping.py")
else:
    st.info("Select at least one file above to begin.")
    if st.button("← Back to overview"):
        st.switch_page("pages/overview.py")

ui.render_sidebar_footer()