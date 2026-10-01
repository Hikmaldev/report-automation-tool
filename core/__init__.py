"""Core package for the Excel/CSV Report Automation Tool.

Contains framework-independent modules (ingestion, cleaning, validation,
reporting, export, config) so the logic can be unit-tested without Streamlit
and reused if the UI later moves to Flask (Design doc §11).
"""