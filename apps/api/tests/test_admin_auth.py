"""Administrator login, lockout, CSRF, role checks and session revocation."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sensoria.modules.admin.auth import (
    MAX_FAILED,
    AdminPrincipal,
    hasher,
    require_role,
    validate_new_password,
)
from sensoria.modules.admin.models import AdminSession, AdminUser
from sensoria.shared.errors import DomainError
from sqlalchemy import select, update

from . import test_cart
from .test_cart import CartEnvironment

cart_environment = test_cart.cart_environment
PASSWORD = "Bardzo-dlugie-haslo-1"
ORIGIN = {"Origin": "http://localhost"}


@pytest_asyncio.fixture
async def admin_env(cart_environment: CartEnvironment) -> AsyncIterator[CartEnvironment]:
    client, factory = cart_environment
    async with factory() as session, session.begin():
        session.add_all(
            [
                AdminUser(
                    email="wlascicielka@example.com",
                    display_name="Właścicielka",
                    password_hash=hasher.hash(PASSWORD),
                    role="owner",
                ),
                AdminUser(
                    email="obsluga@example.com",
                    display_name="Obsługa",
                    password_hash=hasher.hash(PASSWORD),
                    role="staff",
                ),
            ]
        )
    yield client, factory


def _cookie(client: AsyncClient) -> str:
    """Cookies are scoped to /api/admin behind the proxy, so tests forward them explicitly."""
    return f"sensoria_admin_session={client.cookies.get('sensoria_admin_session')}"


async def _login(client: AsyncClient, email: str = "wlascicielka@example.com") -> dict[str, Any]:
    response = await client.post("/admin/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_password_policy() -> None:
    for weak in ("krotkie", "123456789012", "x" * 3):
        with pytest.raises(DomainError):
            validate_new_password(weak)
    validate_new_password(PASSWORD)


@pytest.mark.asyncio
async def test_login_session_csrf_and_logout(admin_env: CartEnvironment) -> None:
    client, _factory = admin_env
    assert (await client.get("/admin/auth/session")).status_code == 401
    body = await _login(client)
    assert body["admin"]["role"] == "owner"
    cookie = _cookie(client)
    session_response = await client.get("/admin/auth/session", headers={"Cookie": cookie})
    assert session_response.json()["admin"]["email"].startswith("wlas")
    rotated = session_response.json()["csrf_token"]
    assert rotated and rotated != body["csrf_token"]
    client.cookies.clear()
    # Unsafe methods need Origin + CSRF header.
    no_csrf = await client.post("/admin/auth/logout", headers={**ORIGIN, "Cookie": cookie})
    assert no_csrf.status_code == 403
    stale = await client.post(
        "/admin/auth/logout",
        headers={**ORIGIN, "X-CSRF-Token": body["csrf_token"], "Cookie": cookie},
    )
    assert stale.status_code == 403  # rotation invalidated the login-time token
    bad_origin = await client.post(
        "/admin/auth/logout",
        headers={
            "Origin": "https://evil.example",
            "X-CSRF-Token": body["csrf_token"],
            "Cookie": cookie,
        },
    )
    assert bad_origin.status_code == 403
    ok = await client.post(
        "/admin/auth/logout",
        headers={**ORIGIN, "X-CSRF-Token": rotated, "Cookie": cookie},
    )
    assert ok.status_code == 204
    revoked = await client.get("/admin/auth/session", headers={"Cookie": cookie})
    assert revoked.status_code == 401  # revoked server-side


@pytest.mark.asyncio
async def test_lockout_after_repeated_failures_and_generic_errors(
    admin_env: CartEnvironment,
) -> None:
    client, factory = admin_env
    unknown = await client.post(
        "/admin/auth/login", json={"email": "nikt@example.com", "password": PASSWORD}
    )
    wrong = await client.post(
        "/admin/auth/login", json={"email": "obsluga@example.com", "password": "zle-haslo-xxxxx"}
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["error"]["message"] == wrong.json()["error"]["message"]
    for _ in range(MAX_FAILED - 1):
        await client.post(
            "/admin/auth/login",
            json={"email": "obsluga@example.com", "password": "zle-haslo-xxxxx"},
        )
    locked = await client.post(
        "/admin/auth/login", json={"email": "obsluga@example.com", "password": PASSWORD}
    )
    assert locked.status_code == 429 and locked.headers["retry-after"] == "900"
    async with factory() as session:
        user = await session.scalar(
            select(AdminUser).where(AdminUser.email == "obsluga@example.com")
        )
        assert user is not None and user.locked_until is not None
        await session.execute(
            update(AdminUser).values(locked_until=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()
    assert (
        await client.post(
            "/admin/auth/login", json={"email": "obsluga@example.com", "password": PASSWORD}
        )
    ).status_code == 200


@pytest.mark.asyncio
async def test_inactive_and_expired_sessions_are_rejected(admin_env: CartEnvironment) -> None:
    client, factory = admin_env
    await _login(client)
    cookie = {"Cookie": _cookie(client)}
    assert (await client.get("/admin/auth/session", headers=cookie)).status_code == 200
    async with factory() as session:
        await session.execute(
            update(AdminSession).values(idle_expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await session.commit()
    assert (await client.get("/admin/auth/session", headers=cookie)).status_code == 401
    await _login(client)
    cookie = {"Cookie": _cookie(client)}
    async with factory() as session:
        await session.execute(update(AdminUser).values(is_active=False))
        await session.commit()
    assert (await client.get("/admin/auth/session", headers=cookie)).status_code == 401


@pytest.mark.asyncio
async def test_role_dependency_blocks_staff_from_owner_only_routes() -> None:
    owner_only = require_role("owner")
    staff = AdminPrincipal(id=uuid4(), role="staff")
    with pytest.raises(DomainError) as error:
        await owner_only(staff)
    assert error.value.status_code == 403
    allowed = AdminPrincipal(id=uuid4(), role="owner")
    assert await owner_only(allowed) is allowed
