"""API error type with plain-language messages (PRD §8.3 Usability).

The public never sees a raw Python traceback: every handled failure carries a
human-readable ``message`` and, where useful, a ``details`` list (e.g. the
names of unmapped required columns).
"""


class ApiError(Exception):
    """An HTTP error that is safe to show to the user."""

    def __init__(self, status: int, message: str, details: list | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.details = details