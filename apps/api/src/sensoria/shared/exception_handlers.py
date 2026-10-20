"""Global exception handlers that keep public responses safe and consistent."""

import logging
import traceback
from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from sensoria.shared.errors import DomainError
from sensoria.shared.schemas import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)


def _error_response(code: str, message: str, status_code: int) -> JSONResponse:
    """Create the standard public error envelope."""

    body = ErrorResponse(error=ErrorDetail(code=code, message=message))
    return JSONResponse(status_code=status_code, content=body.model_dump())


def register_exception_handlers(app: FastAPI, *, development: bool = False) -> None:
    """Register handlers for domain, HTTP, validation, and unexpected errors."""

    @app.exception_handler(DomainError)
    async def handle_domain_error(_request: Request, error: DomainError) -> JSONResponse:
        body = ErrorResponse(error=ErrorDetail(code=error.code, message=error.message))
        return JSONResponse(
            status_code=error.status_code,
            content=body.model_dump(),
            headers=error.headers,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        _request: Request,
        error: StarletteHTTPException,
    ) -> JSONResponse:
        messages: Mapping[int, str] = {
            404: "Nie znaleziono zasobu.",
            405: "Ta metoda żądania nie jest obsługiwana.",
        }
        message = messages.get(error.status_code, "Żądanie nie może być obsłużone.")
        body = ErrorResponse(error=ErrorDetail(code=f"HTTP_{error.status_code}", message=message))
        return JSONResponse(
            status_code=error.status_code,
            content=body.model_dump(),
            headers=error.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request,
        _error: RequestValidationError,
    ) -> JSONResponse:
        return _error_response(
            "REQUEST_VALIDATION_ERROR",
            "Żądanie zawiera nieprawidłowe dane.",
            422,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_request: Request, error: Exception) -> JSONResponse:
        frames = traceback.extract_tb(error.__traceback__)
        stack = "\n".join(f"  {frame.filename}:{frame.lineno} in {frame.name}" for frame in frames)
        logger.error("Unhandled server error [%s]\n%s", type(error).__name__, stack)
        message = "Wystąpił nieoczekiwany błąd serwera."
        if development:
            message = f"Wystąpił nieoczekiwany błąd serwera ({type(error).__name__})."
        return _error_response(
            "INTERNAL_SERVER_ERROR",
            message,
            500,
        )
