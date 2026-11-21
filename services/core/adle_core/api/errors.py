"""The single error shape returned by every endpoint.

Clients (the Electron main process) rely on ``error.code`` being stable. The
error classes themselves live in ``adle_core.errors``; this module turns them,
and everything else that can go wrong, into that one JSON shape.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from adle_core.errors import AdleError
from adle_core.logs import where

logger = logging.getLogger(__name__)


class ErrorBody(BaseModel):
    code: str
    message: str
    detail: Any | None = None
    retry_after_seconds: float | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


def _response(
    status_code: int,
    code: str,
    message: str,
    *,
    detail: Any | None = None,
    retry_after_seconds: float | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(
            code=code, message=message, detail=detail, retry_after_seconds=retry_after_seconds
        )
    )
    headers: dict[str, str] = {}
    if retry_after_seconds is not None:
        headers["Retry-After"] = str(max(0, round(retry_after_seconds)))
    return JSONResponse(
        status_code=status_code, content=body.model_dump(exclude_none=True), headers=headers
    )


def _summarise_validation_errors(exc: RequestValidationError) -> list[dict[str, str]]:
    """Field locations and messages only: never echo submitted values back."""
    return [
        {"field": ".".join(str(part) for part in error["loc"]), "problem": error["msg"]}
        for error in exc.errors()
    ]


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AdleError)
    async def handle_adle_error(_: Request, exc: AdleError) -> JSONResponse:
        return _response(
            exc.status_code,
            exc.code,
            exc.message,
            detail=exc.detail,
            retry_after_seconds=exc.retry_after_seconds,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _response(
            422,
            "invalid_request",
            "The request was not understood.",
            detail=_summarise_validation_errors(exc),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed", 413: "payload_too_large"}.get(
            exc.status_code, "http_error"
        )
        return _response(exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Log the type and location only. Exception messages can carry user content, so
        # the traceback is written without them.
        logger.error(
            "Unhandled %s on %s %s\n%s",
            type(exc).__name__,
            request.method,
            request.url.path,
            where(exc),
        )
        return _response(
            500,
            "internal_error",
            "Something went wrong. Your progress is saved. Please try again.",
        )
