"""Step 5 — Download center: cleaned data, summary report, flagged rows (FR-OUT-04…06).

Downloads go through the service: in API mode the Flask backend generates the
artifacts, in local mode they are built from the materialized frames. Either
way everything is generated in memory — nothing is stored on disk.
"""
import datetime

import streamlit as st

from core import service, theme, ui

ui.init_state()
theme.render_theme()
theme.render_sidebar("downloads")

if not ui.has_data(ui.K_CLEANED):
    ui.render_missing_step([ui.K_CLEANED], "pages/processing.py", "Run cleaning & validation first.")
    ui.render_sidebar_footer()
    st.stop()

sid = ui.api_session_id()
cleaned = st.session_state[ui.K_CLEANED]
clean_subset = st.session_state.get(ui.K_CLEAN_SUBSET)
if clean_subset is None or clean_subset.empty:
    clean_subset = cleaned
flagged = st.session_state.get(ui.K_FLAGGED)
if flagged is None:
    flagged = cleaned.iloc[0:0]

# Remember which summary the user built on the Report page (defaults: region/revenue).
summary_cfg = st.session_state.get(ui.K_SUMMARY_CONFIG) or {}
group_by = summary_cfg.get("group_by") or "region"
agg_col = summary_cfg.get("aggregate") or "revenue"
agg_func = summary_cfg.get("function") or "sum"

summary = st.session_state.get(ui.K_SUMMARY)
if summary is None and "revenue" in clean_subset.columns and "region" in clean_subset.columns:
    # Fallback: build a sensible default summary if the user skipped the report page.
    try:
        summary = service.summary(sid, group_by, agg_col, agg_func, clean_subset)
        st.session_state[ui.K_SUMMARY] = summary
    except ValueError:
        summary = None

theme.page_header(
    "Step 05 · Export",
    "Your report package is ready",
    "Download the clean dataset, summary report, and flagged rows separately — "
    "everything is generated in memory, nothing is stored.",
)

stamp = datetime.date.today().isoformat()

col_clean, col_summary, col_flagged = st.columns(3)

with col_clean:
    st.subheader("📄 Clean dataset")
    st.caption(f"{len(clean_subset):,} validated rows — dates, numbers and text standardized.")
    st.download_button(
        "Download .xlsx",
        data=service.export_bytes(sid, "cleaned", "xlsx", frame=clean_subset),
        file_name=f"clean_dataset_{stamp}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )
    st.download_button(
        "Download .csv",
        data=service.export_bytes(sid, "cleaned", "csv", frame=clean_subset),
        file_name=f"clean_dataset_{stamp}.csv",
        mime="text/csv",
        width="stretch",
    )

with col_summary:
    st.subheader("📊 Summary report")
    if summary is not None:
        st.caption(f"{len(summary):,} group(s) · chart data and table in one workbook.")
        st.download_button(
            "Download .xlsx",
            data=service.export_bytes(
                sid, "summary", "xlsx", frame=summary,
                group_by=group_by, aggregate_column=agg_col, aggregate_func=agg_func,
            ),
            file_name=f"summary_report_{stamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
    else:
        st.caption("No summary available — generate one on the Report page first.")

with col_flagged:
    st.subheader("⚠️ Flagged rows")
    st.caption(f"{len(flagged):,} rows with every reason attached, ready for correction.")
    st.download_button(
        "Download .xlsx",
        data=service.export_bytes(sid, "flagged", "xlsx", frame=flagged),
        file_name=f"flagged_rows_{stamp}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )
    st.download_button(
        "Download .csv",
        data=service.export_bytes(sid, "flagged", "csv", frame=flagged),
        file_name=f"flagged_rows_{stamp}.csv",
        mime="text/csv",
        width="stretch",
    )

st.divider()
st.info("🔒 **Your data stays private.** Nothing is stored after the session — downloads are generated in memory right now.")

back, restart = st.columns([1, 2])
if back.button("← Review table"):
    st.switch_page("pages/review.py")
if restart.button("Start a new report", type="primary", width="stretch"):
    ui.reset_session()
    st.switch_page("pages/upload.py")

ui.render_sidebar_footer()