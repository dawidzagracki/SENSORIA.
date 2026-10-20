"""PostgreSQL-backed account consent, export and closure coverage."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient
from sensoria.modules.accounts.privacy import consent_subject_digest

from .test_accounts_auth import _csrf, _headers


async def _register(client: AsyncClient, email: str) -> tuple[str, str]:
    csrf = await _csrf(client)
    response = await client.post(
        "/accounts/register",
        headers=_headers(csrf),
        json={
            "email": email,
            "password": "A privacy test passphrase",
            "first_name": "Anna",
            "last_name": "Testowa",
        },
    )
    assert response.status_code == 201, response.text
    session = response.cookies.get("sensoria_session")
    csrf_cookie = response.cookies.get("sensoria_csrf")
    assert session and csrf_cookie
    return session, csrf_cookie


def _headers_for_account(session_cookie: str, csrf: str) -> dict[str, str]:
    return _headers(csrf, f"sensoria_session={session_cookie}")


@pytest.mark.asyncio
async def test_consents_are_private_append_only_and_idempotent(
    postgres_client: tuple[AsyncClient, Any],
) -> None:
    client, _engine = postgres_client
    session_cookie, csrf = await _register(client, "privacy@example.test")
    headers = _headers_for_account(session_cookie, csrf)

    denied = await client.get("/accounts/privacy/consents")
    assert denied.status_code == 401

    initial = await client.get(
        "/accounts/privacy/consents", headers={"Cookie": f"sensoria_session={session_cookie}"}
    )
    assert initial.status_code == 200
    assert initial.headers["cache-control"].startswith("private, no-store")
    assert {item["type"]: item["granted"] for item in initial.json()["items"]} == {
        "new_materials": False,
        "voucher_reminders": False,
        "review_requests": False,
    }

    granted = await client.put(
        "/accounts/privacy/consents/voucher_reminders",
        headers=headers,
        json={"granted": True},
    )
    assert granted.status_code == 200
    assert granted.json()["granted"] is True
    duplicate = await client.put(
        "/accounts/privacy/consents/voucher_reminders",
        headers=headers,
        json={"granted": True},
    )
    assert duplicate.status_code == 200
    revoked = await client.put(
        "/accounts/privacy/consents/voucher_reminders",
        headers=headers,
        json={"granted": False},
    )
    assert revoked.status_code == 200

    history = await client.get(
        "/accounts/privacy/consents", headers={"Cookie": f"sensoria_session={session_cookie}"}
    )
    events = [event for event in history.json()["history"] if event["type"] == "voucher_reminders"]
    assert [event["granted"] for event in events] == [True, False]
    assert events[0]["text"] and events[0]["text_version"] == "v1"
    assert all("ip" not in event and "email" not in event for event in events)
    assert consent_subject_digest(" PRIVACY@example.test ") == consent_subject_digest(
        "privacy@example.test"
    )
    assert len(consent_subject_digest("privacy@example.test")) == 64


@pytest.mark.asyncio
async def test_export_request_is_private_idempotent_and_does_not_expose_job_to_other_account(
    postgres_client: tuple[AsyncClient, Any],
) -> None:
    client, _engine = postgres_client
    session_cookie, csrf = await _register(client, "export@example.test")
    headers = _headers_for_account(session_cookie, csrf)

    first = await client.post("/accounts/privacy/export", headers=headers, json={})
    second = await client.post("/accounts/privacy/export", headers=headers, json={})
    assert first.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["status"] in {"pending", "processing"}
    assert "download" not in first.json()

    other_session, _ = await _register(client, "other-export@example.test")
    denied = await client.get(
        f"/accounts/privacy/export/{first.json()['id']}",
        headers={"Cookie": f"sensoria_session={other_session}"},
    )
    assert denied.status_code == 404
    refused = await client.get(
        f"/accounts/privacy/export/{first.json()['id']}/download",
        headers={"Cookie": f"sensoria_session={other_session}"},
    )
    assert refused.status_code == 404


@pytest.mark.asyncio
async def test_delete_requires_email_confirmation_and_immediately_revokes_session(
    postgres_client: tuple[AsyncClient, Any],
) -> None:
    client, _engine = postgres_client
    session_cookie, csrf = await _register(client, "delete@example.test")
    headers = _headers_for_account(session_cookie, csrf)
    wrong_email = await client.post(
        "/accounts/privacy/delete", headers=headers, json={"email": "someone@example.test"}
    )
    assert wrong_email.status_code == 422

    closed = await client.post(
        "/accounts/privacy/delete", headers=headers, json={"email": "delete@example.test"}
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "processing"
    assert "sensoria_session" in closed.headers.get("set-cookie", "")

    blocked = await client.get(
        "/accounts/profile", headers={"Cookie": f"sensoria_session={session_cookie}"}
    )
    assert blocked.status_code == 401
