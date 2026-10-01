"""Overview / home screen — landing dashboard with session metrics."""
import pandas as pd
import streamlit as st

from core import theme, ui

ui.init_state()
theme.render_theme()
theme.render_sidebar("overview")

theme.page_header(
    "Your report workspace",
    "Turn raw exports into trusted reports",
    "Upload your files, review the results, and download a report you can trust.",
)

processed = ui.has_data(ui.K_CLEANED)

if processed:
    raw = st.session_state[ui.K_RAW]
    cleaned = st.session_state[ui.K_CLEANED]
    flagged = st.session_state.get(ui.K_FLAGGED)
    if flagged is None:
        flagged = cleaned.iloc[0:0]
    clean = st.session_state.get(ui.K_CLEAN_SUBSET)
    if clean is None:
        clean = cleaned
    log = st.session_state[ui.K_CLEANING_LOG]

    st.subheader("This session")
    ui.metric_row(
        [
            ("Files processed", f"{len(raw)}"),
            ("Rows consolidated", f"{len(cleaned):,}"),
            ("Duplicates removed", f"{log.get('duplicates_removed', 0):,}"),
            ("Needs review", f"{len(flagged):,}"),
        ]
    )

    st.divider()
    col_a, col_b, col_c = st.columns(3)
    col_a.markdown("**📈 Summary report**  \nCharts and tables from clean rows only.")
    if col_a.button("Open summary report", width="stretch", type="primary", key="ov_report"):
        st.switch_page("pages/report.py")
    col_b.markdown("**⚠️ Review table**  \nFlagged rows with reasons, excluded from the report.")
    if col_b.button("Review flagged rows", width="stretch", key="ov_review"):
        st.switch_page("pages/review.py")
    col_c.markdown("**💾 Download center**  \nClean data, summary, and flagged rows.")
    if col_c.button("Go to downloads", width="stretch", key="ov_downloads"):
        st.switch_page("pages/downloads.py")

    with st.expander("Cleaning log — every automatic change", expanded=False):
        if log:
            st.dataframe(
                pd.DataFrame(list(log.items()), columns=["Change", "Count"]),
                hide_index=True,
                width="stretch",
            )
        else:
            st.caption("No changes recorded yet.")

    st.progress(1.0, text="Workflow: Upload → Map → Process → Report → Export")
else:
    st.markdown(
        "Upload several Excel or CSV files, let the tool clean and validate them, "
        "then build a consolidated summary — all in one session."
    )
    ui.metric_row(
        [
            ("Upload multiple files", ".xlsx and .csv"),
            ("Cleaned automatically", "duplicates, dates, numbers"),
            ("Flagged for review", "nothing is silently dropped"),
            ("Export anytime", "Excel or CSV"),
        ]
    )

    st.divider()
    first, second, third = st.columns(3)
    with first:
        st.markdown("**1 · Upload**  \nAdd your raw exports in one go.")
    with second:
        st.markdown("**2 · Clean & validate**  \nReview mapping, see what changed, fix flagged rows.")
    with third:
        st.markdown("**3 · Report & download**  \nSummaries, charts, and clean exports.")

    if st.button("Start by uploading files", type="primary"):
        st.switch_page("pages/upload.py")

    with st.expander("No data is ever stored", expanded=False):
        st.caption(
            "Files are processed in memory for your current session only. "
            "Nothing is uploaded to an external service, and the session clears when you reset or leave."
        )

ui.render_sidebar_footer()