"""Health endpoint tests; readiness uses real PostgreSQL in the success case."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.asyncio
async def test_health_executes_select_one_on_postgres(
    postgres_client: tuple[AsyncClient, AsyncEngine],
) -> None:
    client, engine = postgres_client
    statements: list[str] = []

    def record_statement(
        _connection: Connection,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        _context: Any,
        _executemany: bool,
    ) -> None:
        statements.append(statement.strip().upper())

    event.listen(engine.sync_engine, "before_cursor_execute", record_statement)
    try:
        response = await client.get("/health")
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", record_statement)

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": "0.2.0",
        "database": "ok",
    }
    assert "SELECT 1" in statements


@pytest.mark.asyncio
async def test_health_returns_503_when_database_query_fails(
    api_client: AsyncClient,
) -> None:
    from collections.abc import Callable
    from typing import NoReturn

    from sensoria.database import get_session
    from sensoria.main import app
    from sqlalchemy.exc import OperationalError

    class UnavailableSession:
        async def execute(self, _statement: Any) -> NoReturn:
            raise OperationalError("SELECT 1", {}, OSError("simulated outage"))

    async def unavailable_session() -> UnavailableSession:
        return UnavailableSession()

    previous_override: Callable[..., Any] | None = app.dependency_overrides.get(get_session)
    app.dependency_overrides[get_session] = unavailable_session
    try:
        response = await api_client.get("/health")
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_session, None)
        else:
            app.dependency_overrides[get_session] = previous_override

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "DATABASE_UNAVAILABLE",
            "message": "Baza danych jest chwilowo niedostępna.",
        }
    }
