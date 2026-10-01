"""Bridge between Werkzeug's upload objects and the framework-independent core.

``core.ingestion`` was written against Streamlit's ``UploadedFile`` API, where
``.name`` is the file name and ``.getvalue()`` returns the bytes. Werkzeug's
``FileStorage`` uses ``.name`` for the form field name (the real name lives in
``.filename``) and has no ``getvalue``. This adapter normalizes the difference
so the exact same parsing code serves both frontends.
"""
from __future__ import annotations

import io

from werkzeug.datastructures import FileStorage


class UploadedFileAdapter:
    """Presents a Werkzeug ``FileStorage`` with the Streamlit-style upload API."""

    def __init__(self, storage: FileStorage):
        self._storage = storage
        self.name = storage.filename or ""
        self._buffer: io.BytesIO | None = None

    def _buf(self) -> io.BytesIO:
        if self._buffer is None:
            self._storage.stream.seek(0)
            self._buffer = io.BytesIO(self._storage.stream.read())
        return self._buffer

    @property
    def size(self) -> int:
        """Byte length of the uploaded file (FR-UP-04)."""
        return len(self._buf().getvalue())

    def getvalue(self) -> bytes:
        return self._buf().getvalue()

    # --- minimal file-like surface for pandas / openpyxl ---
    def read(self, *args) -> bytes:
        return self._buf().read(*args)

    def seek(self, offset: int, whence: int = 0) -> int:
        return self._buf().seek(offset, whence)

    def tell(self) -> int:
        return self._buf().tell()

    def close(self) -> None:  # noqa: D401 - expected by some readers
        pass