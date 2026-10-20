"""Database-backed health endpoint."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.database import get_session
from sensoria.shared.errors import DomainError
from sensoria.shared.schemas import HealthResponse
from sensoria.version import APP_VERSION

logger = logging.getLogger(__name__)
router = APIRouter()
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health(session: SessionDependency) -> HealthResponse:
    """Return ready only after PostgreSQL successfully executes SELECT 1."""

    try:
        result = await session.execute(text("SELECT 1"))
        if result.scalar_one() != 1:
            raise SQLAlchemyError("Health query returned an unexpected result")
    except (SQLAlchemyError, TimeoutError, OSError) as error:
        logger.warning("Database health query failed")
        raise DomainError(
            code="DATABASE_UNAVAILABLE",
            message="Baza danych jest chwilowo niedostępna.",
            status_code=503,
        ) from error

    return HealthResponse(status="ok", version=APP_VERSION, database="ok")
