"""Step 2 — Column mapping (FR-CLN-06).

Shows every source column found across the uploaded files and lets the user
confirm or adjust which standard field each one maps to before cleaning runs.
"""
import pandas as pd
import streamlit as st

from core import config, ingestion, theme, ui

ui.init_state()
theme.render_theme()
theme.render_sidebar("upload")

if not ui.has_data(ui.K_RAW):
    ui.render_missing_step([ui.K_RAW], "pages/upload.py", "Upload some files first, then come back to map columns.")
    ui.render_sidebar_footer()
    st.stop()

records = st.session_state[ui.K_RAW]
frame = ingestion.build_mapping_frame(records)

# Merge any previously confirmed edits with freshly detected columns.
previous = st.session_state.get(ui.K_MAPPING_FRAME)
if previous is not None and not previous.empty:
    merged = frame.merge(
        previous[["source_column", "standard_field"]],
        on="source_column",
        how="left",
        suffixes=("", "_saved"),
    )
    merged["standard_field"] = merged["standard_field_saved"].fillna(merged["standard_field"])
else:
    merged = frame

display = merged[["source_column", "files", "example", "standard_field"]].copy()
display["standard_field"] = display["standard_field"].fillna("").replace("", "")

theme.page_header(
    "Step 02 · Preparation",
    "Match your columns",
    "Source files use different column names. Choose the standard field each column "
    "belongs to; columns mapped to 'ignore' are dropped from the combined dataset.",
)

options = list(config.CANONICAL_FIELDS) + [config.IGNORE_LABEL]
editor_key = f"mapping_editor_{len(records)}_{len(display)}"

edited = st.data_editor(
    display,
    column_config={
        "source_column": st.column_config.TextColumn("Source column", disabled=True, width="medium"),
        "files": st.column_config.TextColumn("Found in files", disabled=True),
        "example": st.column_config.TextColumn("Example value", disabled=True),
        "standard_field": st.column_config.SelectboxColumn(
            "Standard field", options=options, required=True, help="Map to a standard field or ignore the column."
        ),
    },
    hide_index=True,
    key=editor_key,
    width="stretch",
)

# Persist the table so edits survive navigation.
if edited is not None and not edited.empty:
    st.session_state[ui.K_MAPPING_FRAME] = edited.copy()

column_map = dict(zip(edited["source_column"], edited["standard_field"]))
missing = ingestion.missing_required_columns(column_map)

if missing:
    st.warning(
        "**Missing required columns:** " + ", ".join(missing) + ". "
        "Map a source column to each of these before processing can continue."
    )

with st.expander("Required fields for this report", expanded=False):
    st.caption("Rows missing any of these fields will be flagged, not deleted (FR-VAL-01).")
    for col in config.REQUIRED_COLUMNS:
        state = "✓ mapped" if col in column_map.values() else "— not mapped yet"
        st.markdown(f"- **`{col}`** · {state}")

if st.button("Confirm mapping & continue →", type="primary", disabled=bool(missing)):
    st.session_state[ui.K_COLUMN_MAP] = column_map
    mapped = ingestion.apply_mapping(records, column_map)
    st.session_state[ui.K_MAPPED] = mapped
    st.success(f"Combined dataset ready: {len(mapped):,} rows across {len(records)} file(s).")
    st.switch_page("pages/processing.py")

ui.render_sidebar_footer()