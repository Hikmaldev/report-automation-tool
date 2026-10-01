"""In-memory session store (FR-SES-01, FR-SES-02).

Sessions live only in RAM: restarting the backend clears them, idle sessions
are pruned by TTL, and nothing is ever written to disk. Each session mirrors
the Streamlit frontend's state (files, mapping, cleaned/flagged frames).
"""
from __future__ import annotations

import copy
import threading
import time
import uuid
from collections import OrderedDict

from flask import current_app

from .errors import ApiError

# Data shape every session starts with. DataFrames are stored per session and
# dropped automatically when the session expires or is reset.
_EMPTY = {
    "files": [],  # list of dicts: {name, df, rows, columns, size_bytes}
    "upload_errors": [],  # list of dicts: {file, message}
    "total_bytes": 0,
    "mapping": {},  # confirmed source column -> standard field
    "mapped": None,  # DataFrame after column mapping (FR-CLN-06)
    "cleaned": None,  # DataFrame after cleaning
    "flagged": None,  # DataFrame of rows failing validation (FR-VAL-03)
    "clean_subset": None,  # rows that are safe for reporting (FR-VAL-05)
    "cleaning_log": None,  # every automatic change, visible to the user
    "processed": False,
}


class SessionStore:
    """Thread-safe, TTL-pruned store keyed by opaque session id."""

    def __init__(self, ttl_seconds: int = 30 * 60, max_sessions: int = 64):
        self._ttl = ttl_seconds
        self._max = max_sessions
        self._lock = threading.RLock()
        self._sessions: "OrderedDict[str, dict]" = OrderedDict()

    def _prune(self) -> None:
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items() if now - s["last_active"] > self._ttl
        ]
        for sid in expired:
            del self._sessions[sid]
        while len(self._sessions) > self._max:
            self._sessions.popitem(last=False)

    def create(self) -> str:
        """Create a new session and return its id."""
        with self._lock:
            self._prune()
            sid = uuid.uuid4().hex
            # Deep copy: the empty template contains mutable containers
            # (lists) that must never be shared between sessions.
            self._sessions[sid] = {
                "created": time.time(),
                "last_active": time.time(),
                "data": copy.deepcopy(_EMPTY),
            }
            return sid

    def _touch(self, sid: str) -> bool:
        s = self._sessions.get(sid)
        if s is None or time.time() - s["last_active"] > self._ttl:
            return False
        s["last_active"] = time.time()
        self._sessions.move_to_end(sid)
        return True

    def get(self, sid: str) -> dict:
        """Return the session's mutable data dict, or raise KeyError."""
        with self._lock:
            if not self._touch(sid):
                raise KeyError(sid)
            return self._sessions[sid]["data"]

    def reset(self, sid: str) -> None:
        """Clear all data but keep the same session id (FR-SES-02)."""
        with self._lock:
            if not self._touch(sid):
                raise KeyError(sid)
            self._sessions[sid]["data"] = copy.deepcopy(_EMPTY)

    def delete(self, sid: str) -> bool:
        with self._lock:
            return self._sessions.pop(sid, None) is not None


def store() -> SessionStore:
    """Current application's session store."""
    return current_app.extensions["session_store"]


def session_data(sid: str) -> dict:
    """Fetch a session's data or raise a user-safe 404."""
    try:
        return store().get(sid)
    except KeyError:
        raise ApiError(
            404,
            "Session not found or expired. Create a new one with POST /api/sessions.",
        )