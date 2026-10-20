"""Test configuration and isolated PostgreSQL fixtures."""

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from dotenv import dotenv_values
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

API_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = API_ROOT.parents[1]
_local_environment = dotenv_values(REPOSITORY_ROOT / ".env")
_application_database_url = os.environ.get("DATABASE_URL") or _local_environment.get("DATABASE_URL")
_test_database_url = os.environ.get("TEST_DATABASE_URL") or _local_environment.get(
    "TEST_DATABASE_URL"
)

if _test_database_url:
    os.environ["TEST_DATABASE_URL"] = _test_database_url
    if _application_database_url:
        application = make_url(_application_database_url)
        test = make_url(_test_database_url)
        application_identity = (
            application.drivername,
            application.username,
            application.host,
            application.port,
            application.database,
        )
        test_identity = (
            test.drivername,
            test.username,
            test.host,
            test.port,
            test.database,
        )
        if application_identity == test_identity:
            raise RuntimeError("TEST_DATABASE_URL musi wskazywać osobną bazę testową.")
    os.environ["DATABASE_URL"] = _test_database_url
else:
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://sensoria:sensoria@127.0.0.1:5432/sensoria_test",
    )

os.environ["ENVIRONMENT"] = "development"
os.environ["SECRET_KEY"] = "test-only-placeholder-not-a-secret"


@pytest.fixture
def test_database_url() -> str:
    """Require a dedicated PostgreSQL database whose name ends in `_test`."""

    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.fail("Ustaw TEST_DATABASE_URL wskazujące na oddzielną bazę PostgreSQL 16.")
    parsed_url = make_url(value)
    if parsed_url.drivername != "postgresql+asyncpg":
        pytest.fail("TEST_DATABASE_URL musi używać sterownika PostgreSQL asyncpg.")
    if not parsed_url.database or not parsed_url.database.endswith("_test"):
        pytest.fail("Nazwa bazy TEST_DATABASE_URL musi kończyć się na _test.")
    return value


@pytest_asyncio.fixture
async def api_client() -> AsyncIterator[AsyncClient]:
    """Create an HTTP client without starting a server process."""

    from sensoria.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest_asyncio.fixture
async def postgres_client(
    test_database_url: str,
) -> AsyncIterator[tuple[AsyncClient, AsyncEngine]]:
    """Use one outer transaction per test and roll it back before closing connections."""

    from sensoria.database import get_session
    from sensoria.main import app

    await asyncio.to_thread(command.upgrade, Config(str(API_ROOT / "alembic.ini")), "head")

    test_engine = create_async_engine(
        test_database_url,
        pool_pre_ping=True,
        pool_timeout=3,
        connect_args={"timeout": 3, "command_timeout": 3},
    )
    try:
        async with test_engine.connect() as connection:
            outer_transaction = await connection.begin()
            test_session_factory = async_sessionmaker(
                bind=connection,
                class_=AsyncSession,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )

            async def override_get_session() -> AsyncIterator[AsyncSession]:
                async with test_session_factory() as session:
                    try:
                        yield session
                    except BaseException:
                        await session.rollback()
                        raise

            app.dependency_overrides[get_session] = override_get_session
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                ) as client:
                    yield client, test_engine
            finally:
                app.dependency_overrides.pop(get_session, None)
                if outer_transaction.is_active:
                    await outer_transaction.rollback()
    finally:
        await test_engine.dispose()


@pytest_asyncio.fixture
async def postgres_independent_client(
    test_database_url: str,
) -> AsyncIterator[AsyncClient]:
    """Run requests with independent PostgreSQL sessions for concurrency tests."""

    from sensoria.database import get_session
    from sensoria.main import app

    await asyncio.to_thread(command.upgrade, Config(str(API_ROOT / "alembic.ini")), "head")
    test_engine = create_async_engine(
        test_database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=0,
        connect_args={"timeout": 5, "command_timeout": 5},
    )
    session_factory = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def independent_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
            except BaseException:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = independent_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)
        await test_engine.dispose()
