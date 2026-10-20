"""Async SQLAlchemy engine, session factory, metadata base, and request dependency."""

from collections.abc import AsyncIterator
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from sensoria.config import get_settings

settings = get_settings()
engine = create_async_engine(
    settings.DATABASE_URL.get_secret_value(),
    echo=False,
    hide_parameters=True,
    pool_pre_ping=True,
    pool_timeout=3,
    connect_args={"timeout": 3, "command_timeout": 3},
)
SessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Shared model base with deterministic constraint and index names."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDMixin:
    """Application-generated UUID primary key shared by persisted models."""

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)


class TimestampMixin:
    """Database-created timestamps; SQLAlchemy updates ``updated_at`` on ORM writes."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped session and roll back failed request transactions."""

    async with SessionFactory() as session:
        try:
            yield session
        except BaseException:
            await session.rollback()
            raise
