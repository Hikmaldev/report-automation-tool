"""Clearpath — Excel/CSV Report Automation Tool (Streamlit MVP).

Entry point for the multipage app. Pages are defined with st.Page and
registered through st.navigation (Streamlit >= 1.36). Each page script under
``pages/`` renders one screen of the user flow; all shared state lives in
``st.session_state`` so navigation keeps the pipeline intact.
"""
import streamlit as st

st.set_page_config(
    page_title="Clearpath · Report Automation",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

pages = [
    st.Page("pages/overview.py", title="Overview", icon="🏠", default=True, url_path="overview"),
    st.Page("pages/upload.py", title="Upload files", icon="📤", url_path="upload"),
    st.Page("pages/column_mapping.py", title="Column mapping", icon="🔗", url_path="mapping"),
    st.Page("pages/processing.py", title="Processing", icon="⚙️", url_path="processing"),
    st.Page("pages/report.py", title="Summary report", icon="📈", url_path="report"),
    st.Page("pages/review.py", title="Review table", icon="⚠️", url_path="review"),
    st.Page("pages/downloads.py", title="Download center", icon="💾", url_path="downloads"),
]

# Navigation menu is hidden: every page renders the custom styled sidebar
# (brand + nav) via core.theme, matching the HTML mockup.
pg = st.navigation(pages, position="hidden")
pg.run()