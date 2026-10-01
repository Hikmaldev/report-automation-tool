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
K_API_SID = "api_session_id"

# Derived keys that become meaningless when the uploaded files change.
_DERIVED_KEYS = (
    K_MAPPING_FRAME,
    K_COLUMN_MAP,
    K_MAPPED,
    K_CLEANED,
    K_FLAGGED,
    K_CLEAN_SUBSET,
    K_CLEANING_LOG,
    K_SUMMARY,
    K_SUMMARY_CONFIG,
)

_DEFAULTS = {
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
    K_API_SID: None,
}


def init_state() -> None:
    """Seed session_state with empty containers (idempotent)."""
    for key, value in _DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value


def api_session_id() -> str | None:
    """Id of the backend session (API mode), created lazily; None when local."""
    from core import service

    if service.backend_mode() != "api":
        return None
    if not st.session_state.get(K_API_SID):
        st.session_state[K_API_SID] = service.new_session()
    return st.session_state[K_API_SID]


def clear_derived_state() -> None:
    """Reset processing results because the input files changed."""
    for key in _DERIVED_KEYS:
        st.session_state[key] = None if key != K_COLUMN_MAP and key != K_SUMMARY_CONFIG else (
            {} if key == K_COLUMN_MAP else {"group_by": None, "aggregate": None, "function": "sum"}
        )


def reset_session() -> None:
    """Clear all session data (FR-SES-02) without restarting the app."""
    from core import service

    sid = st.session_state.get(K_API_SID)
    if sid:
        service.reset_session(sid)
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def render_sidebar_footer() -> None:
    """Privacy note + backend indicator + reset control under the navigation."""
    with st.sidebar:
        st.markdown("---")
        st.caption("🔒 **Your data stays private**  \nFiles are processed in memory for this session and never stored.")
        from core import service

        info = service.backend_info()
        if info["mode"] == "api":
            st.caption(f"⚙️ **Backend:** API · `{info['url']}`")
        else:
            st.caption("⚙️ **Backend:** local (in-process pipeline)")
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