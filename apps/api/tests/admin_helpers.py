"""Shared helpers for tests that exercise the authenticated admin API."""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient
from sensoria.modules.admin.auth import hasher
from sensoria.modules.admin.models import AdminUser
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

PASSWORD = "Bardzo-dlugie-haslo-1"


async def create_admin(
    factory: async_sessionmaker[AsyncSession], email: str, role: str = "owner"
) -> None:
    async with factory() as session, session.begin():
        session.add(
            AdminUser(
                email=email,
                display_name=email.split("@")[0],
                password_hash=hasher.hash(PASSWORD),
                role=role,
            )
        )


async def admin_headers(client: AsyncClient, email: str) -> dict[str, str]:
    """Log in and return the Cookie/Origin/CSRF headers the browser would send."""
    response = await client.post("/admin/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    cookie = client.cookies.get("sensoria_admin_session")
    client.cookies.clear()
    return {
        "Cookie": f"sensoria_admin_session={cookie}",
        "Origin": "http://localhost",
        "X-CSRF-Token": body["csrf_token"],
    }
