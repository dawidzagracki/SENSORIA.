"""Async Alembic environment using application settings and metadata."""

import asyncio
import importlib
import pkgutil
from typing import Any

import sensoria.modules
from alembic import context
from alembic.autogenerate.api import AutogenContext
from sensoria.config import get_settings
from sensoria.database import Base
from sensoria.modules.catalog.types import (
    DigitalLabelType,
    ProductKindType,
    ProductStatusType,
    VoucherVariantKindType,
)
from sensoria.shared.audit_log import ActorTypeType
from sensoria.shared.types import Money, VatRateType
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

config = context.config
settings = get_settings()
target_metadata = Base.metadata


def render_database_type(type_: str, obj: Any, autogen_context: AutogenContext) -> str | bool:
    """Render validated application types as portable PostgreSQL DDL types."""

    del autogen_context
    if type_ != "type":
        return False
    if isinstance(obj, Money):
        return "sa.BigInteger()"
    if isinstance(
        obj,
        (
            VatRateType,
            ActorTypeType,
            ProductKindType,
            ProductStatusType,
            VoucherVariantKindType,
            DigitalLabelType,
        ),
    ):
        return f"sa.String(length={obj.impl.length})"
    return False


def import_model_modules() -> None:
    """Import future models so they register with Base.metadata for autogeneration."""

    importlib.import_module("sensoria.shared.app_settings")
    importlib.import_module("sensoria.shared.audit_log")
    prefix = f"{sensoria.modules.__name__}."
    for module in pkgutil.walk_packages(sensoria.modules.__path__, prefix=prefix):
        if module.name.endswith(".models"):
            importlib.import_module(module.name)


def run_migrations_offline() -> None:
    """Run migrations without a DBAPI connection, using the configured URL."""

    context.configure(
        url=settings.DATABASE_URL.get_secret_value(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_item=render_database_type,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Configure Alembic against a synchronous connection adapted by SQLAlchemy."""

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_item=render_database_type,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations through SQLAlchemy's async engine."""

    engine = create_async_engine(
        settings.DATABASE_URL.get_secret_value(),
        poolclass=pool.NullPool,
        connect_args={"timeout": 5, "command_timeout": 5},
    )
    try:
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await engine.dispose()


import_model_modules()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
