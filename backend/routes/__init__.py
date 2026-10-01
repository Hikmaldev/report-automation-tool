"""Blueprint registry.

Keeps the app factory tidy; each route module owns one resource group that
mirrors a screen of the Streamlit frontend (upload, mapping, process, report,
export).
"""
from . import export as _export
from . import health as _health
from . import mapping as _mapping
from . import process as _process
from . import report as _report
from . import upload as _upload

_BLUEPRINTS = (
    _health.bp,
    _upload.bp,
    _mapping.bp,
    _process.bp,
    _report.bp,
    _export.bp,
)


def register_blueprints(app) -> None:
    for blueprint in _BLUEPRINTS:
        app.register_blueprint(blueprint)