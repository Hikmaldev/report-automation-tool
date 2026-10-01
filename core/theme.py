"""Visual identity layer: mirrors the static HTML design (styles.css/workflow.css).

Streamlit renders native widgets, so we inject a shared stylesheet plus small
HTML helpers (sidebar brand/nav, page headers) to reproduce the planned look:
cream/green palette, Fraunces serif headings, card-style metrics, tinted
sidebar and buttons.
"""
from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# Navigation descriptor used by the custom sidebar (order matches the design).
# ---------------------------------------------------------------------------
NAV_ITEMS = [
    ("overview", "Overview", "❏", "pages/overview.py"),
    ("upload", "Upload files", "⇪", "pages/upload.py"),
    ("report", "Reports", "◫", "pages/report.py"),
    ("review", "Review table", "⚑", "pages/review.py"),
    ("downloads", "Download center", "⇓", "pages/downloads.py"),
]

BRAND_HTML = """
<div class="cp-brand"><span class="cp-brand-mark"><i></i><i></i><i></i></span>clearpath</div>
"""

THEME_CSS = """
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Fraunces:wght@600;700&display=swap');

/* ---- base ---- */
html, body, [class*="css"], .stApp {
    font-family: 'DM Sans', Arial, sans-serif;
}
.stApp { background-color: #f7f9f8; color: #20272c; }
[data-testid="stAppViewContainer"] { background-color: #f7f9f8; }
[data-testid="stMain"] { padding-top: 1.2rem; }
[data-testid="stFooter"] { visibility: hidden; height: 0; }

.stMarkdown h1, .stMarkdown h2, .stMarkdown h3,
[data-testid="stHeading"] h1, [data-testid="stHeading"] h2, [data-testid="stHeading"] h3 {
    font-family: 'Fraunces', Georgia, serif;
    color: #243039;
    letter-spacing: -0.4px;
}
.stMarkdown p, .stWrite { color: #56615f; }

/* ---- sidebar ---- */
[data-testid="stSidebar"] {
    background: #f1f6f2;
    border-right: 1px solid #e3ebe5;
}
[data-testid="stSidebarContent"] { padding-top: 1.4rem; }
[data-testid="stSidebar"] .stButton > button {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 10px;
    justify-content: flex-start;
    text-align: left;
    background: transparent;
    border: none;
    color: #697774;
    font-weight: 600;
    border-radius: 8px;
    padding: 11px 13px;
    font-size: 0.82rem;
    transition: background .15s ease;
}
[data-testid="stSidebar"] .stButton > button:hover { background: #deede6; color: #286b5a; }
[data-testid="stSidebar"] .stButton { margin-bottom: 2px; }

.cp-brand {
    display: flex; align-items: center; gap: 9px;
    color: #293f3c;
    font-family: 'Fraunces', Georgia, serif;
    font-size: 1.35rem; font-weight: 700; letter-spacing: -0.8px;
    padding: 0 4px 6px;
}
.cp-brand-mark { position: relative; width: 23px; height: 20px; display: inline-block; }
.cp-brand-mark i { position: absolute; bottom: 1px; width: 6px; border-radius: 4px 4px 1px 1px; background: #3c8b74; transform: skewY(-22deg); }
.cp-brand-mark i:nth-child(1) { height: 9px; left: 0; opacity: .7; }
.cp-brand-mark i:nth-child(2) { height: 15px; left: 8px; }
.cp-brand-mark i:nth-child(3) { height: 20px; left: 16px; opacity: .8; }

.cp-nav-item {
    display: flex; align-items: center; gap: 10px;
    padding: 11px 13px; margin-bottom: 2px;
    border-radius: 8px;
    color: #697774; font-weight: 600; font-size: 0.82rem;
    position: relative;
}
.cp-nav-active { background: #deede6; color: #286b5a; }
.cp-nav-active::before {
    content: ''; position: absolute; left: -1.05rem;
    width: 3px; height: 22px; border-radius: 0 3px 3px 0; background: #3c8b74;
}
.cp-nav-icon { width: 18px; text-align: center; font-size: 0.95rem; }
.cp-nav-badge {
    margin-left: auto; min-width: 21px; height: 20px; padding: 0 6px;
    display: inline-flex; align-items: center; justify-content: center;
    border-radius: 10px; background: #fce4d0; color: #b86529; font-size: 0.65rem;
}
.cp-ws-label {
    margin: 1.4rem 0 0.8rem; color: #a5ada9;
    font-size: 0.62rem; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase;
}

/* ---- page header (eyebrow + serif title + sub) ---- */
.cp-header { margin: 0.2rem 0 1.4rem; }
.cp-eyebrow {
    margin: 0 0 7px; color: #9ba5a2;
    font-size: 0.62rem; font-weight: 700; letter-spacing: 1.3px; text-transform: uppercase;
}
.cp-title {
    margin: 0; color: #243039;
    font-family: 'Fraunces', Georgia, serif; font-size: 1.85rem; font-weight: 600;
    letter-spacing: -1px;
}
.cp-sub { margin: 9px 0 0; color: #87928f; font-size: 0.8rem; max-width: 640px; }

/* ---- metric cards ---- */
[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid #e4e9e8;
    border-radius: 8px;
    padding: 17px 19px;
    box-shadow: 0 5px 16px rgba(38,52,55,.035);
}
[data-testid="stMetricLabel"] p {
    color: #88938f; font-size: 0.68rem; font-weight: 600; text-transform: uppercase; letter-spacing: .5px;
}
[data-testid="stMetricValue"] {
    color: #26333a;
    font-family: 'Fraunces', Georgia, serif;
    font-size: 1.75rem; font-weight: 600; letter-spacing: -0.6px;
}
[data-testid="stMetricDelta"] { font-size: 0.68rem; }

/* ---- buttons ---- */
.stButton > button, .stDownloadButton > button {
    border-radius: 6px; font-weight: 600; transition: all .15s ease;
}
[data-testid="stBaseButton-primary"] button {
    background: #243039; color: #ffffff; border: none;
}
[data-testid="stBaseButton-primary"] button:hover { background: #304453; color: #fff; }
[data-testid="stBaseButton-secondary"] button {
    background: #ffffff; color: #6f817a; border: 1px solid #dfe7e3;
}
[data-testid="stBaseButton-secondary"] button:hover { background: #f4faf6; color: #286b5a; }

/* ---- file uploader ---- */
[data-testid="stFileUploaderDropzone"] {
    border: 1px dashed #a9d0ba; border-radius: 8px; background: #fcfefd;
}

/* ---- panels / expanders / dataframes ---- */
[data-testid="stExpander"] {
    border: 1px solid #e4eae7; border-radius: 8px; background: #ffffff;
}
[data-testid="stDataFrame"] {
    border: 1px solid #e4eae7; border-radius: 8px; overflow: hidden;
    box-shadow: 0 5px 16px rgba(38,52,55,.035);
}

/* ---- alerts ---- */
[data-testid="stAlert"] { border-radius: 8px; }
.stInfo { background: #f3f9f5; border-color: #dcebe1; }
.stWarning { background: #fff8f2; border-color: #f1dfd1; }

/* ---- captions & dividers ---- */
[data-testid="stCaptionContainer"] p { color: #a0aaa6; }
[data-testid="stHorizontalBlock"] { gap: 0.9rem; }
hr { border-color: #e4e9e8; }
"""


def render_theme() -> None:
    """Inject the shared stylesheet (call at the top of every page)."""
    st.markdown(f"<style>{THEME_CSS}</style>", unsafe_allow_html=True)


def page_header(eyebrow: str, title: str, subtitle: str = "") -> None:
    """Render the styled page heading used across all screens."""
    sub = f'<p class="cp-sub">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f'<div class="cp-header"><p class="cp-eyebrow">{eyebrow}</p>'
        f'<h1 class="cp-title">{title}</h1>{sub}</div>',
        unsafe_allow_html=True,
    )


def render_sidebar(current: str) -> None:
    """Custom sidebar matching the HTML mockup: brand, nav, active state."""
    with st.sidebar:
        st.markdown(BRAND_HTML, unsafe_allow_html=True)
        st.markdown('<div class="cp-ws-label">Workspace</div>', unsafe_allow_html=True)

        flagged = st.session_state.get("flagged_df", None)
        badge_count = len(flagged) if flagged is not None and hasattr(flagged, "__len__") else 0

        for key, label, icon, target in NAV_ITEMS:
            if key == current:
                badge = f'<span class="cp-nav-badge">{badge_count}</span>' if key == "review" and badge_count else ""
                st.markdown(
                    f'<div class="cp-nav-item cp-nav-active"><span class="cp-nav-icon">{icon}</span>{label}{badge}</div>',
                    unsafe_allow_html=True,
                )
            else:
                badge = f" {badge_count}" if key == "review" and badge_count else ""
                if st.button(f"{icon} {label}{badge}", key=f"nav_{key}"):
                    st.switch_page(target)