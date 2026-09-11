"""Application error types and a uniform JSON error envelope.

Every failure the client can act on is reported as::

    {"error": {"code": "voice_not_found", "message": "...", "details": {...}}}

A stable machine-readable ``code`` matters more than the HTTP status here: the
web app, and later the Android/iOS clients, branch on it.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

# Spelled numerically: Starlette renamed these constants and deprecated the old
# names, and the new ones do not exist on older releases.
_HTTP_413 = 413
_HTTP_422 = 422


class AppError(Exception):
    """Base class for errors that map to a deliberate HTTP response."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class VoiceNotFoundError(NotFoundError):
    code = "voice_not_found"


class GenerationNotFoundError(NotFoundError):
    code = "generation_not_found"


class ValidationError(AppError):
    status_code = _HTTP_422
    code = "validation_error"


class AudioValidationError(ValidationError):
    code = "invalid_audio"


class ConsentRequiredError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "consent_required"


class PayloadTooLargeError(AppError):
    status_code = _HTTP_413
    code = "payload_too_large"


class RateLimitedError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"

    def __init__(self, message: str, *, retry_after: int, details: dict[str, Any] | None = None):
        super().__init__(message, details=details)
        self.retry_after = retry_after


class QuotaExceededError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "quota_exceeded"


class EngineUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "engine_unavailable"


class SynthesisFailedError(AppError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "synthesis_failed"


class UnsupportedLanguageError(ValidationError):
    code = "unsupported_language"


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return body


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        headers = {}
        if isinstance(exc, RateLimitedError):
            headers["Retry-After"] = str(exc.retry_after)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, exc.details),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _request_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [
            {
                "field": ".".join(str(part) for part in err["loc"][1:]) or str(err["loc"][0]),
                "message": err["msg"],
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=_HTTP_422,
            content=error_body(
                "validation_error", "Request validation failed.", {"fields": fields}
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed", 413: "payload_too_large"}.get(
            exc.status_code, "http_error"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code, str(exc.detail)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Log the detail; never leak stack traces or filesystem paths to clients.
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_body("internal_error", "An unexpected error occurred."),
        )
