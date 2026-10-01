"""Application factory (Flask pattern from the official docs).

Registers blueprints, CORS, and JSON error handlers so every failure returns
a plain-language JSON message and never a raw traceback (PRD §8.3).
"""
from __future__ import annotations

import logging

from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from core import config
from .errors import ApiError
from .routes import register_blueprints
from .sessions import SessionStore

logger = logging.getLogger(__name__)


def create_app(test_config: dict | None = None) -> Flask:
    """Build and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_mapping(
        MAX_FILE_SIZE_MB=config.MAX_FILE_SIZE_MB,
        MAX_TOTAL_UPLOAD_MB=config.MAX_TOTAL_UPLOAD_MB,
        SESSION_TTL_SECONDS=30 * 60,
        MAX_SESSIONS=64,
        CORS_ORIGINS="*",  # local/single-user tool; tighten for shared hosting
    )
    if test_config:
        app.config.update(test_config)

    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    app.extensions["session_store"] = SessionStore(
        ttl_seconds=app.config["SESSION_TTL_SECONDS"],
        max_sessions=app.config["MAX_SESSIONS"],
    )

    register_blueprints(app)

    # ------------------------------------------------------------------ #
    # Error handling: JSON everywhere under /api/, plain language only.
    # ------------------------------------------------------------------ #
    @app.errorhandler(ApiError)
    def handle_api_error(exc: ApiError):
        payload = {"error": exc.message}
        if exc.details is not None:
            payload["details"] = exc.details
        return jsonify(payload), exc.status

    @app.errorhandler(ValueError)
    def handle_value_error(exc: ValueError):
        # Invalid user choices (e.g. bad group column) carry plain messages.
        return jsonify({"error": str(exc)}), 400

    @app.errorhandler(HTTPException)
    def handle_http_error(exc: HTTPException):
        if request.path.startswith("/api/"):
            return jsonify({"error": exc.description or exc.name}), exc.code
        return exc

    @app.errorhandler(Exception)
    def handle_unexpected(exc: Exception):
        logger.exception("Unhandled error while serving %s", request.path)
        if request.path.startswith("/api/"):
            return jsonify(
                {"error": "Something went wrong while processing your request."}
            ), 500
        return exc

    @app.get("/")
    def index():
        return jsonify(
            {
                "service": "Report Automation Tool API",
                "version": "1.0.0",
                "first_step": "POST /api/sessions",
            }
        )

    return app