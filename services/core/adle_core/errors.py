"""Expected, recoverable failures.

These carry a stable ``code`` (safe for the interface to branch on) and a
message written for the learner: specific, constructive, free of internals.
This module has no framework imports so that every layer, including parser
worker processes, can use it cheaply.
"""

from __future__ import annotations

from typing import Any


class AdleError(Exception):
    """An expected failure with a stable code and a readable message."""

    status_code = 400
    code = "bad_request"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        detail: Any | None = None,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.detail = detail
        self.retry_after_seconds = retry_after_seconds


class NotFoundError(AdleError):
    status_code = 404
    code = "not_found"


class ConflictError(AdleError):
    status_code = 409
    code = "conflict"


class ValidationFailedError(AdleError):
    status_code = 422
    code = "invalid_request"


class UnauthorizedError(AdleError):
    status_code = 401
    code = "unauthorized"
