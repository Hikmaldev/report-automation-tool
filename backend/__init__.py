"""Flask REST API backend for the Report Automation Tool.

Reuses the framework-independent pipeline in ``core/`` (PRD §9.3) as-is:
ingestion, cleaning, validation, reporting and export logic live in ``core``,
this package only exposes them over HTTP with in-memory per-session state
(PRD §6.5 FR-SES-01/02).

Run with:
    python -m backend.wsgi
    # or
    flask --app backend.wsgi run
"""
from .app import create_app

__all__ = ["create_app"]