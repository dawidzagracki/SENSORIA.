"""Passwordless login-link request and consumption flows."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sensoria.modules.accounts.mail_jobs import (
    build_auth_email_link,
    cleanup_login_link_payloads,
    login_link_email_content,
)
from sensoria.modules.accounts.models import AuthAttempt, AuthEmailJob, Customer, LoginLink
from sensoria.modules.accounts.router import safe_login_return_path
from sensoria.shared.audit_log import AuditLog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .test_accounts_auth import _csrf, _headers


def test_login_return_path_rejects_encoded_open_redirects() -> None:
    assert safe_login_return_path("/konto/vouchery") == "/konto/vouchery"
    # The account landing page exists; /konto/biblioteka is not implemented yet.
    assert safe_login_return_path("//evil.example") == "/konto"
    assert safe_login_return_path("/%252f%252fevil.example") == "/konto"
    assert safe_login_return_path("https://evil.example") == "/konto"


def test_login_email_uses_private_path_token_and_mentions_one_time_expiry() -> None:
    link = build_auth_email_link("login_link", "opaque-secret", "https://sensoria.shop")
    assert link == "https://sensoria.shop/konto/link-logowania/opaque-secret"
    assert "?token=" not in link
    subject, html_body, text_body = login_link_email_content(link)
    assert subject == "Zaloguj się do SENSORIA"
    assert "Zaloguj się" in html_body
    assert "ważny przez 15 minut" in text_body
    assert "jednorazowy" in text_body
    assert "Jeśli nie prosiłaś o ten link, zignoruj tę wiadomość." in text_body


@pytest.mark.asyncio
async def test_login_link_response_is_generic_and_never_creates_account(
    postgres_client: tuple[AsyncClient, Any],
) -> None:
    client, _engine = postgres_client
    csrf = await _csrf(client)
    payload = {"email": "missing-login-link@example.test"}
    unknown = await client.post("/auth/login-link", headers=_headers(csrf), json=payload)
    assert unknown.status_code == 200
    assert unknown.json() == {
        "message": "Jeśli konto istnieje, wyślemy wiadomość z linkiem do logowania."
    }

    known_registration = await client.post(
        "/accounts/register",
        headers=_headers(csrf),
        json={
            "email": "link-owner@example.test",
            "password": "a proper account passphrase",
            "first_name": "Anna",
            "last_name": "Właścicielka",
        },
    )
    assert known_registration.status_code == 201
    known = await client.post(
        "/auth/login-link",
        headers=_headers(csrf),
        json={"email": " LINK-OWNER@EXAMPLE.TEST ", "return_to": "/konto/vouchery"},
    )
    assert known.status_code == unknown.status_code
    assert known.json() == unknown.json()
    assert "token" not in known.text.lower()


@pytest.mark.asyncio
async def test_login_link_get_is_non_consuming_and_confirmation_sets_session(
    postgres_client: tuple[AsyncClient, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _engine = postgres_client
    csrf = await _csrf(client)
    registered = await client.post(
        "/accounts/register",
        headers=_headers(csrf),
        json={
            "email": "magic@example.test",
            "password": "a proper account passphrase",
            "first_name": "Maja",
            "last_name": "Linkowa",
        },
    )
    assert registered.status_code == 201

    from sensoria.modules.accounts import router as accounts_router
    from sensoria.modules.accounts.purchase_linking import PurchaseLinkingResult

    raw_token = "A" * 43
    monkeypatch.setattr(accounts_router, "_new_login_link_token", lambda: raw_token)
    request = await client.post(
        "/auth/login-link",
        headers=_headers(csrf),
        json={"email": "magic@example.test", "return_to": "/konto/vouchery"},
    )
    monkeypatch.undo()
    assert request.status_code == 200
    checked = await client.get(f"/auth/login-link/{raw_token}")
    assert checked.status_code == 200
    assert checked.json() == {"valid": True}
    assert not checked.headers.get("set-cookie")
    head = await client.head(f"/auth/login-link/{raw_token}")
    assert head.status_code == 204

    csrf = await _csrf(client)
    calls: list[str] = []

    async def record_linking_call(session: Any, customer_id: Any, *, source: str, at: Any) -> Any:
        del session, customer_id, at
        calls.append(source)
        return PurchaseLinkingResult(orders_linked=2)

    monkeypatch.setattr(accounts_router, "reconcile_guest_purchases", record_linking_call)
    confirmed = await client.post(f"/auth/login-link/{raw_token}", headers=_headers(csrf), json={})
    assert confirmed.status_code == 200
    assert confirmed.json()["redirect_to"] == "/konto/vouchery"
    assert confirmed.json()["purchase_linking"]["orders_linked"] == 2
    assert calls == ["login_link"]
    session_cookie = confirmed.cookies.get("sensoria_session")
    assert session_cookie
    cookie_header = {"Cookie": f"sensoria_session={session_cookie}"}
    current = await client.get("/accounts/session", headers=cookie_header)
    assert current.status_code == 200
    assert current.json()["customer"]["email"] == "magic@example.test"
    repeated = await client.post(f"/auth/login-link/{raw_token}", headers=_headers(csrf), json={})
    assert repeated.status_code == 400


@pytest.mark.asyncio
async def test_login_link_expiration_boundary_and_supersession(
    postgres_client: tuple[AsyncClient, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, engine = postgres_client
    csrf = await _csrf(client)
    registered = await client.post(
        "/accounts/register",
        headers=_headers(csrf),
        json={
            "email": "link-expiry@example.test",
            "password": "a proper account passphrase",
            "first_name": "Ewa",
            "last_name": "Testowa",
        },
    )
    assert registered.status_code == 201
    from sensoria.modules.accounts import router as accounts_router

    tokens = iter(("B" * 43, "C" * 43))
    monkeypatch.setattr(accounts_router, "_new_login_link_token", lambda: next(tokens))
    first = await client.post(
        "/auth/login-link", headers=_headers(csrf), json={"email": "link-expiry@example.test"}
    )
    second = await client.post(
        "/auth/login-link", headers=_headers(csrf), json={"email": "link-expiry@example.test"}
    )
    monkeypatch.undo()
    assert first.status_code == second.status_code == 200
    assert (await client.get(f"/auth/login-link/{'B' * 43}")).json() == {"valid": False}
    assert (await client.get(f"/auth/login-link/{'C' * 43}")).json() == {"valid": True}

    fixed_now = datetime.now(UTC)
    monkeypatch.setattr(accounts_router, "utc_now", lambda: fixed_now)
    monkeypatch.setattr(accounts_router, "_new_login_link_token", lambda: "E" * 43)
    boundary_request = await client.post(
        "/auth/login-link",
        headers=_headers(csrf),
        json={"email": "link-expiry@example.test"},
    )
    assert boundary_request.status_code == 200
    monkeypatch.setattr(accounts_router, "utc_now", lambda: fixed_now + timedelta(minutes=15))
    expired = await client.get(f"/auth/login-link/{'E' * 43}")
    assert expired.json() == {"valid": False}


@pytest.mark.asyncio
async def test_rate_limit_is_generic_and_does_not_invalidate_current_link(
    postgres_client: tuple[AsyncClient, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _engine = postgres_client
    csrf = await _csrf(client)
    registered = await client.post(
        "/accounts/register",
        headers=_headers(csrf),
        json={
            "email": "link-rate@example.test",
            "password": "a proper account passphrase",
            "first_name": "Ala",
            "last_name": "Limit",
        },
    )
    assert registered.status_code == 201
    from sensoria.modules.accounts import router as accounts_router

    tokens = iter(("F" * 43, "G" * 43, "H" * 43))
    monkeypatch.setattr(accounts_router, "_new_login_link_token", lambda: next(tokens))
    known_responses = [
        await client.post(
            "/auth/login-link",
            headers=_headers(csrf),
            json={"email": "link-rate@example.test"},
        )
        for _ in range(4)
    ]
    unknown_responses = [
        await client.post(
            "/auth/login-link",
            headers=_headers(csrf),
            json={"email": "unknown-rate@example.test"},
        )
        for _ in range(4)
    ]
    monkeypatch.undo()
    assert [response.status_code for response in known_responses] == [200, 200, 200, 429]
    assert [response.status_code for response in unknown_responses] == [200, 200, 200, 429]
    assert known_responses[0].json() == unknown_responses[0].json()
    assert known_responses[3].json() == unknown_responses[3].json()
    assert known_responses[3].headers.get("retry-after") == "900"
    assert (await client.get(f"/auth/login-link/{'H' * 43}")).json() == {"valid": True}


@pytest.mark.asyncio
async def test_parallel_login_link_consumption_has_one_winner(
    test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Use independent committed PostgreSQL connections (not the rollback fixture)."""
    from sensoria.database import get_session
    from sensoria.main import app
    from sensoria.modules.accounts import router as accounts_router

    api_root = Path(__file__).resolve().parents[1]
    await asyncio.to_thread(command.upgrade, Config(str(api_root / "alembic.ini")), "head")
    engine = create_async_engine(test_database_url, pool_size=4, max_overflow=0)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def session_dependency() -> AsyncIterator[Any]:
        async with factory() as db:
            yield db

    app.dependency_overrides[get_session] = session_dependency
    email = f"race-{uuid4().hex}@example.test"
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as setup:
            csrf = await _csrf(setup)
            registered = await setup.post(
                "/accounts/register",
                headers=_headers(csrf),
                json={
                    "email": email,
                    "password": "a proper account passphrase",
                    "first_name": "Ola",
                    "last_name": "Równoległa",
                },
            )
            assert registered.status_code == 201
            raw_token = "D" * 43
            monkeypatch.setattr(accounts_router, "_new_login_link_token", lambda: raw_token)
            requested = await setup.post(
                "/auth/login-link", headers=_headers(csrf), json={"email": email}
            )
            monkeypatch.undo()
            assert requested.status_code == 200
            async with factory() as db:
                customer = await db.scalar(select(Customer).where(Customer.email == email))
                assert customer is not None
                link = await db.scalar(
                    select(LoginLink).where(LoginLink.customer_id == customer.id)
                )
                assert link is not None
                assert link.token_hash != raw_token
                assert (
                    abs((link.expires_at - link.created_at - timedelta(minutes=15)).total_seconds())
                    < 2
                )
                assert link.used_at is None
                job = await db.get(AuthEmailJob, link.email_job_id)
                assert job is not None and job.purpose == "login_link"
                assert raw_token not in job.payload_ciphertext

        csrf = "race-csrf-token-value-long-enough"
        headers = _headers(csrf)

        async def consume() -> int:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://localhost",
                cookies={"sensoria_csrf": csrf},
            ) as consumer:
                response = await consumer.post(
                    f"/auth/login-link/{raw_token}", headers=headers, json={}
                )
                return response.status_code

        statuses = await asyncio.gather(consume(), consume())
        assert statuses.count(200) == 1
        assert sum(status in {400, 429} for status in statuses) == 1
        async with factory() as db:
            customer = await db.scalar(select(Customer).where(Customer.email == email))
            assert customer is not None
            link = await db.scalar(select(LoginLink).where(LoginLink.customer_id == customer.id))
            assert link is not None and link.used_at is not None
            job = await db.get(AuthEmailJob, link.email_job_id)
            assert job is not None
            assert raw_token not in job.payload_ciphertext
            audit_entries = list(
                (
                    await db.scalars(
                        select(AuditLog).where(
                            AuditLog.actor_id == customer.id,
                        )
                    )
                ).all()
            )
            assert any(entry.action == "login_link_used" for entry in audit_entries)
            assert all(raw_token not in str(entry.payload) for entry in audit_entries)
            expired_created_at = datetime.now(UTC) - timedelta(days=1)
            link.created_at = expired_created_at
            link.expires_at = expired_created_at + timedelta(minutes=15)
            await db.commit()
        assert await cleanup_login_link_payloads(factory) == 1
        async with factory() as db:
            customer = await db.scalar(select(Customer).where(Customer.email == email))
            assert customer is not None
            link = await db.scalar(select(LoginLink).where(LoginLink.customer_id == customer.id))
            assert link is not None
            job = await db.get(AuthEmailJob, link.email_job_id)
            assert job is not None
            assert job.payload_ciphertext == ""
            assert job.status == "cancelled"
    finally:
        app.dependency_overrides.pop(get_session, None)
        async with factory() as db:
            customer = await db.scalar(select(Customer).where(Customer.email == email))
            if customer is not None:
                await db.execute(delete(LoginLink).where(LoginLink.customer_id == customer.id))
                await db.execute(
                    delete(AuthEmailJob).where(AuthEmailJob.customer_id == customer.id)
                )
                await db.execute(delete(Customer).where(Customer.id == customer.id))
                await db.execute(delete(AuditLog).where(AuditLog.actor_id == customer.id))
            # The rate-limit audit events deliberately use a system actor and
            # reference AuthAttempt rows, so remove this test's audit footprint
            # from the committed PostgreSQL integration database as well.
            await db.execute(
                delete(AuditLog).where(
                    AuditLog.action.in_(
                        {
                            "login_link_requested",
                            "login_link_rate_limited",
                            "login_link_rejected",
                            "login_link_used",
                            "session_created",
                        }
                    )
                )
            )
            await db.execute(delete(AuthAttempt))
            await db.commit()
        await engine.dispose()
