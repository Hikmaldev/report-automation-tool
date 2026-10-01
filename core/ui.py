"""Small UI helpers shared across pages (Design doc §7)."""
from __future__ import annotations

import streamlit as st

# Keys mirrored from Design doc §7.
K_RAW = "raw_dataframes"
K_FILE_ERRORS = "file_errors"
K_REMOVED = "removed_files"
K_MAPPING_FRAME = "mapping_frame"
K_COLUMN_MAP = "column_map"
K_MAPPED = "mapped_df"
K_CLEANED = "cleaned_df"
K_FLAGGED = "flagged_df"
K_CLEAN_SUBSET = "clean_df"
K_CLEANING_LOG = "cleaning_log"
K_SUMMARY = "summary_df"
K_SUMMARY_CONFIG = "summary_config"


def init_state() -> None:
    """Seed session_state with empty containers (idempotent)."""
    defaults = {
        K_RAW: [],
        K_FILE_ERRORS: [],
        K_REMOVED: set(),
        K_MAPPING_FRAME: None,
        K_COLUMN_MAP: {},
        K_MAPPED: None,
        K_CLEANED: None,
        K_FLAGGED: None,
        K_CLEAN_SUBSET: None,
        K_CLEANING_LOG: {},
        K_SUMMARY: None,
        K_SUMMARY_CONFIG: {"group_by": None, "aggregate": None, "function": "sum"},
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_session() -> None:
    """Clear all session data (FR-SES-02) without restarting the app."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def render_sidebar_footer() -> None:
    """Privacy note + reset control shown under the navigation menu."""
    with st.sidebar:
        st.markdown("---")
        st.caption("🔒 **Your data stays private**  \nFiles are processed in memory for this session and never stored.")
        if st.button("Reset session", width="stretch", type="secondary", key="reset_session"):
            reset_session()
            st.rerun()


def has_data(key: str) -> bool:
    return bool(st.session_state.get(key) is not None and not (
        isinstance(st.session_state.get(key), (list, dict, set)) and len(st.session_state.get(key)) == 0
    ))


def render_missing_step(required: list[str], next_page: str, message: str) -> None:
    """Show a friendly 'you must finish an earlier step' notice."""
    st.info(message)
    left, _ = st.columns([1, 2])
    if left.button("Go to the next step", type="primary"):
        st.switch_page(next_page)


def metric_row(metrics: list[tuple[str, str]]) -> None:
    """Render a row of metric cards."""
    cols = st.columns(len(metrics))
    for col, (label, value) in zip(cols, metrics):
        col.metric(label, value)