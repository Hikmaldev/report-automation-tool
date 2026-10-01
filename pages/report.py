"""Step 4 — Summary report: grouping controls, chart, summary table (FR-OUT)."""
import plotly.express as px
import streamlit as st

from core import config, reporting, theme, ui


def _safe_index(options: list[str], preferred: str) -> int:
    """Index of ``preferred`` in options, or 0 when absent."""
    return options.index(preferred) if preferred in options else 0


ui.init_state()
theme.render_theme()
theme.render_sidebar("report")

if not ui.has_data(ui.K_CLEANED):
    ui.render_missing_step([ui.K_CLEANED], "pages/processing.py", "Run cleaning & validation first.")
    ui.render_sidebar_footer()
    st.stop()

cleaned = st.session_state[ui.K_CLEANED]
clean_subset = st.session_state.get(ui.K_CLEAN_SUBSET)
if clean_subset is None or clean_subset.empty:
    clean_subset = cleaned
flagged = st.session_state.get(ui.K_FLAGGED)
flagged_count = len(flagged) if flagged is not None else 0

theme.page_header(
    "Step 04 · Reporting",
    "Explore your clean report",
    "Build a summary from trusted rows — flagged rows are excluded by default.",
)

if flagged_count:
    st.info(f"**{flagged_count:,} flagged rows are excluded** from this report by default.")

# ---- Controls (FR-OUT-03) -------------------------------------------------
data_columns = [c for c in clean_subset.columns if c != "_source_file"]
numeric_columns = list(clean_subset.select_dtypes(include="number").columns)
group_options = data_columns
agg_options = data_columns if numeric_columns else []

c1, c2, c3, c4 = st.columns(4)
group_by = c1.selectbox("Group rows by", group_options, index=_safe_index(group_options, "region"))
agg_col = c2.selectbox("Aggregate column", agg_options, index=_safe_index(agg_options, "revenue"))
func_label = c3.selectbox(
    "Aggregate function", list(config.AGGREGATE_FUNCTIONS.keys()), index=0
)
chart_type = c4.radio("Chart type", ["Bar", "Line"], horizontal=True)

if not agg_options:
    st.error("No numeric columns were found in the clean dataset, so no summary can be computed.")
    ui.render_sidebar_footer()
    st.stop()

aggregate_func = config.AGGREGATE_FUNCTIONS[func_label]

try:
    summary = reporting.build_summary(clean_subset, group_by, agg_col, aggregate_func)
except ValueError as exc:
    st.error(str(exc))
    ui.render_sidebar_footer()
    st.stop()

st.session_state[ui.K_SUMMARY] = summary
st.session_state[ui.K_SUMMARY_CONFIG] = {
    "group_by": group_by,
    "aggregate": agg_col,
    "function": aggregate_func,
    "function_label": func_label,
}

# ---- Chart (FR-OUT-02) -----------------------------------------------------
labels = summary[group_by].astype(str).tolist()
values = summary[agg_col].tolist()

fig = px.bar(
    summary, x=group_by, y=agg_col, color=group_by,
    text_auto=".3s", title=f"{func_label} of {agg_col} by {group_by[0].upper() + group_by[1:]}",
    color_discrete_sequence=["#7ab294", "#9ac7a9", "#b6d9bb", "#d3e9d4", "#5a9c80"],
) if chart_type == "Bar" else px.line(
    summary, x=group_by, y=agg_col, markers=True,
    title=f"{func_label} of {agg_col} by {group_by[0].upper() + group_by[1:]}",
    color_discrete_sequence=["#7ab294", "#9ac7a9", "#b6d9bb", "#d3e9d4", "#5a9c80"],
)
fig.update_layout(
    title_x=0.05, margin=dict(t=50, b=25, l=10, r=10), height=380,
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig, width="stretch")

# ---- Summary table (FR-OUT-01) ---------------------------------------------
st.subheader("Summary table")
col_config = {
    group_by: st.column_config.TextColumn(group_by),
    agg_col: st.column_config.NumberColumn(
        agg_col,
        format="$ ,.0f" if agg_col == "revenue" else ",.2f",
    ),
}
st.dataframe(summary, hide_index=True, width="stretch", column_config=col_config)

total = summary[agg_col].sum()
st.caption(f"**Total: {total:,.2f}** across {len(summary):,} group(s) from {len(clean_subset):,} clean rows.")

ui.render_sidebar_footer()