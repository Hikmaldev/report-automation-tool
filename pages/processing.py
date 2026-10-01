"""Step 3 — Processing result (cleaning + validation with a visible log)."""
import pandas as pd
import streamlit as st

from core import cleaning, config, theme, ui, validation

ui.init_state()
theme.render_theme()
theme.render_sidebar("upload")

if not ui.has_data(ui.K_MAPPED):
    ui.render_missing_step([ui.K_MAPPED], "pages/column_mapping.py", "Confirm your column mapping first.")
    ui.render_sidebar_footer()
    st.stop()

mapped = st.session_state[ui.K_MAPPED]

theme.page_header(
    "Step 03 · Cleaning & validation",
    "Your data is ready to review",
    "We combine your files, clean safe inconsistencies, and set aside any rows "
    "that need a human look — nothing is silently removed.",
)


def run_pipeline(source_df: pd.DataFrame) -> None:
    """Clean + validate in-memory and store results in session state."""
    with st.status("Running cleaning & validation…", expanded=True) as status:
        st.write("Removing exact duplicates…")
        cleaned, dups = cleaning.deduplicate(source_df)
        log = {"duplicates_removed": dups}

        st.write("Standardizing dates (YYYY-MM-DD)…")
        cleaned = cleaning.standardize_dates(cleaned, config.DATE_COLUMNS, log)

        st.write("Standardizing numbers (currencies, separators)…")
        cleaned = cleaning.standardize_numbers(cleaned, config.NUMERIC_COLUMNS, log)

        st.write("Standardizing text (whitespace, casing)…")
        cleaned = cleaning.standardize_text(cleaned, config.TEXT_COLUMNS, config.CASING_COLUMNS, log)

        st.write("Validating required fields and formats…")
        masks = validation.validate_required_fields_by_column(cleaned, config.REQUIRED_COLUMNS)
        masks.update(
            validation.validate_types(cleaned, source_df, config.NUMERIC_COLUMNS, config.DATE_COLUMNS)
        )
        flagged = validation.build_review_table(cleaned, masks)
        clean_subset, flagged = validation.split_clean_and_flagged(cleaned, flagged)

        status.update(label="Processing complete", state="complete", expanded=False)

    st.session_state[ui.K_CLEANED] = cleaned
    st.session_state[ui.K_FLAGGED] = flagged
    st.session_state[ui.K_CLEAN_SUBSET] = clean_subset
    st.session_state[ui.K_CLEANING_LOG] = log


if st.button("Run cleaning & validation", type="primary"):
    run_pipeline(mapped)
    st.rerun()

if ui.has_data(ui.K_CLEANED):
    cleaned = st.session_state[ui.K_CLEANED]
    flagged = st.session_state[ui.K_FLAGGED]
    clean_subset = st.session_state[ui.K_CLEAN_SUBSET]
    log = st.session_state[ui.K_CLEANING_LOG]

    st.divider()
    ui.metric_row(
        [
            ("Files processed", f"{len(st.session_state[ui.K_RAW])}"),
            ("Rows combined", f"{len(mapped):,}"),
            ("Duplicates removed", f"{log.get('duplicates_removed', 0):,}"),
            ("Rows flagged", f"{len(flagged):,}"),
            ("Clean rows for reporting", f"{len(clean_subset):,}"),
        ]
    )

    if len(flagged):
        st.warning(
            f"**{len(flagged):,} rows were flagged and excluded from the summary.** "
            "Nothing was silently dropped — review them before exporting."
        )
    else:
        st.success("No rows were flagged. Every row passed required-field and format checks.")

    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("Cleaning log (FR-CLN-07)")
        log_rows = [{"Change": k.replace("_", " ").title(), "Count": v} for k, v in log.items()]
        st.dataframe(pd.DataFrame(log_rows), hide_index=True, width="stretch")
    with col_right:
        st.subheader("Beyond the numbers")
        st.write(
            "Automatic cleaning only fixes safe, deterministic inconsistencies: "
            "exact duplicates, date/number formats, whitespace, and casing. "
            "Anything questionable becomes a **flagged row**, never a silent change."
        )

    st.divider()
    back, report, review = st.columns([1, 2, 2])
    if back.button("← Column mapping"):
        st.switch_page("pages/column_mapping.py")
    if report.button("View summary report →", type="primary", width="stretch"):
        st.switch_page("pages/report.py")
    if review.button("Review flagged rows →", width="stretch"):
        st.switch_page("pages/review.py")

ui.render_sidebar_footer()