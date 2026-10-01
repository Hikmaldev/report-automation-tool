"""Review table — flagged rows with reasons and a scoped download (FR-VAL-03/04)."""
import pandas as pd
import streamlit as st

from core import export, theme, ui

ui.init_state()
theme.render_theme()
theme.render_sidebar("review")

if not ui.has_data(ui.K_CLEANED):
    ui.render_missing_step([ui.K_CLEANED], "pages/processing.py", "Run cleaning & validation first.")
    ui.render_sidebar_footer()
    st.stop()

cleaned = st.session_state[ui.K_CLEANED]
flagged = st.session_state.get(ui.K_FLAGGED)

theme.page_header(
    "Validation review",
    "Rows that need your attention",
    "These rows were excluded from your report because a required field is "
    "missing or a value could not be validated.",
)

if flagged is None or flagged.empty:
    st.success("No flagged rows. Every row passed required-field and format checks.")
    ui.render_sidebar_footer()
    st.stop()

st.info(
    f"**{len(flagged):,} rows flagged** out of {len(cleaned):,} total rows. "
    "Flagged rows never appear in summary charts or tables (FR-VAL-05)."
)

# ---- Filters ---------------------------------------------------------------
reasons = sorted({r for reason in flagged["_flag_reason"] for r in str(reason).split("; ")})
filter_col, search_col = st.columns([2, 3])
reason_filter = filter_col.selectbox("Filter by reason", ["All reasons"] + reasons)
query = search_col.text_input("Search order id / customer", placeholder="e.g. ORD-10482").strip()

view = flagged
if reason_filter != "All reasons":
    view = view[view["_flag_reason"].str.contains(reason_filter, na=False)]
if query:
    search_cols = [c for c in ("order_id", "customer", "_source_row") if c in view.columns]
    if search_cols:
        haystack = view[search_cols].astype("string").agg(" ".join, axis=1)
        view = view[haystack.str.contains(query, case=False, na=False)]

st.caption(f"Showing {len(view):,} of {len(flagged):,} flagged rows.")

# ---- Table ------------------------------------------------------------------
display_cols = ["_source_row", "_flag_reason"] + [c for c in flagged.columns if c not in ("_source_row", "_flag_reason")]
view_display = view[display_cols].rename(columns={"_source_row": "Row", "_flag_reason": "Reason(s)"}).copy()
column_config = {
    "Row": st.column_config.NumberColumn("Row in cleaned dataset"),
    "Reason(s)": st.column_config.TextColumn("Reason(s)", width="small"),
}
st.dataframe(view_display, hide_index=True, width="stretch", column_config=column_config)

# ---- Scoped download (FR-VAL-04) --------------------------------------------
st.subheader("Download flagged rows for correction")
d1, d2 = st.columns(2)
d1.download_button(
    "Download as .xlsx",
    data=export.to_excel_bytes(view.reset_index(drop=True), sheet_name="Flagged rows"),
    file_name="flagged_rows.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    width="stretch",
)
d2.download_button(
    "Download as .csv",
    data=export.to_csv_bytes(view.reset_index(drop=True)),
    file_name="flagged_rows.csv",
    mime="text/csv",
    width="stretch",
)

st.divider()
back, forward = st.columns([1, 2])
if back.button("← Back to report"):
    st.switch_page("pages/report.py")
if forward.button("Continue to download center →", type="primary", width="stretch"):
    st.switch_page("pages/downloads.py")

ui.render_sidebar_footer()