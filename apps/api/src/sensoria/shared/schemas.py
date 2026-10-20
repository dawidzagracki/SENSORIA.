"""Shared response schemas."""

from typing import Literal

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Stable public error fields."""

    code: str
    message: str


class ErrorResponse(BaseModel):
    """Envelope shared by application, HTTP, and validation errors."""

    error: ErrorDetail


class HealthResponse(BaseModel):
    """Readiness response returned only after a successful database query."""

    status: Literal["ok"]
    version: str
    database: Literal["ok"]
