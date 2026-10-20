"""Private profile, email-change and saved-address API coverage."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

from .test_accounts_auth import _csrf, _headers


async def _register(client: AsyncClient, email: str) -> tuple[str, str]:
    csrf = await _csrf(client)
    response = await client.post(
        "/accounts/register",
        headers=_headers(csrf),
        json={
            "email": email,
            "password": "A usable profile test passphrase",
            "first_name": "Anna",
            "last_name": "Testowa",
        },
    )
    assert response.status_code == 201, response.text
    session = response.cookies.get("sensoria_session")
    csrf_cookie = response.cookies.get("sensoria_csrf")
    assert session and csrf_cookie
    return session, csrf_cookie


def _account_headers(session_cookie: str, csrf: str) -> dict[str, str]:
    return _headers(csrf, f"sensoria_session={session_cookie}")


@pytest.mark.asyncio
async def test_profile_personal_data_and_saved_address_default_invariant(
    postgres_client: tuple[AsyncClient, Any],
) -> None:
    client, _engine = postgres_client
    session_cookie, csrf = await _register(client, "profile@example.test")

    profile = await client.get(
        "/accounts/profile", headers={"Cookie": f"sensoria_session={session_cookie}"}
    )
    assert profile.status_code == 200
    assert profile.headers["cache-control"].startswith("private, no-store")
    assert profile.json()["addresses"] == []

    headers = _account_headers(session_cookie, csrf)
    updated = await client.put(
        "/accounts/profile/personal",
        headers=headers,
        json={"first_name": " Anna  Maria ", "last_name": " Nowa ", "phone": " 123 456 789 "},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json() == {
        "first_name": "Anna Maria",
        "last_name": "Nowa",
        "phone": "123 456 789",
    }

    first = await client.post(
        "/accounts/profile/addresses",
        headers=_account_headers(session_cookie, csrf),
        json={
            "label": "Dom",
            "address_type": "address",
            "street": "Długa",
            "building_number": "4A",
            "apartment_number": "7",
            "postal_code": "10-001",
            "city": "Olsztyn",
            "country": "PL",
        },
    )
    assert first.status_code == 201, first.text
    assert first.json()["is_default"] is True
    first_id = first.json()["id"]

    second = await client.post(
        "/accounts/profile/addresses",
        headers=_account_headers(session_cookie, csrf),
        json={
            "label": "Praca",
            "address_type": "address",
            "street": "Krótka",
            "building_number": "12",
            "postal_code": "10-002",
            "city": "Olsztyn",
            "country": "PL",
        },
    )
    assert second.status_code == 201, second.text
    second_id = second.json()["id"]
    assert second.json()["is_default"] is False
    checkout = await client.get(
        "/accounts/checkout-defaults",
        headers={"Cookie": f"sensoria_session={session_cookie}"},
    )
    assert checkout.status_code == 200
    assert checkout.json()["first_name"] == "Anna Maria"
    assert len(checkout.json()["addresses"]) == 2
    assert checkout.json()["addresses"][0]["is_default"] is True

    duplicate = await client.post(
        "/accounts/profile/addresses",
        headers=_account_headers(session_cookie, csrf),
        json={
            "label": "Inna nazwa",
            "address_type": "address",
            "street": "Długa",
            "building_number": "4A",
            "apartment_number": "7",
            "postal_code": "10-001",
            "city": "Olsztyn",
            "country": "PL",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "ADDRESS_ALREADY_SAVED"

    selected = await client.post(
        f"/accounts/profile/addresses/{second_id}/default",
        headers=_account_headers(session_cookie, csrf),
    )
    assert selected.status_code == 200
    listing = await client.get(
        "/accounts/profile/addresses", headers={"Cookie": f"sensoria_session={session_cookie}"}
    )
    assert sum(item["is_default"] for item in listing.json()["items"]) == 1
    assert next(item for item in listing.json()["items"] if item["id"] == second_id)["is_default"]

    deleted_default = await client.delete(
        f"/accounts/profile/addresses/{second_id}",
        headers=_account_headers(session_cookie, csrf),
    )
    assert deleted_default.status_code == 200
    remaining = await client.get(
        "/accounts/profile/addresses", headers={"Cookie": f"sensoria_session={session_cookie}"}
    )
    assert len(remaining.json()["items"]) == 1
    assert remaining.json()["items"][0]["id"] == first_id
    assert remaining.json()["items"][0]["is_default"] is True

    deleted_last = await client.delete(
        f"/accounts/profile/addresses/{first_id}",
        headers=_account_headers(session_cookie, csrf),
    )
    assert deleted_last.status_code == 200
    empty = await client.get(
        "/accounts/profile/addresses", headers={"Cookie": f"sensoria_session={session_cookie}"}
    )
    assert empty.json()["items"] == []


@pytest.mark.asyncio
async def test_profile_rejects_foreign_address_and_invalid_address_shape(
    postgres_client: tuple[AsyncClient, Any],
) -> None:
    client, _engine = postgres_client
    session_cookie, csrf = await _register(client, "address-owner@example.test")
    headers = _account_headers(session_cookie, csrf)

    foreign = await client.delete(
        "/accounts/profile/addresses/00000000-0000-0000-0000-000000000099",
        headers=headers,
    )
    assert foreign.status_code == 404

    invalid = await client.post(
        "/accounts/profile/addresses",
        headers=_account_headers(session_cookie, csrf),
        json={
            "label": "Punkt",
            "address_type": "parcel_locker",
            "point_code": "FAKE",
            "street": "Nie może być tutaj",
        },
    )
    assert invalid.status_code == 422


@pytest_asyncio.fixture
async def purge_concurrent_customers(test_database_url: str) -> AsyncIterator[None]:
    """Independent sessions commit for real, so remove their customers afterwards."""
    yield
    engine = create_async_engine(test_database_url)
    try:
        async with engine.begin() as connection:
            await connection.exec_driver_sql(
                "DELETE FROM customers WHERE email LIKE 'concurrent-address-%'"
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_first_addresses_leave_exactly_one_default(
    postgres_independent_client: AsyncClient,
    purge_concurrent_customers: None,
) -> None:
    client = postgres_independent_client
    session_cookie, csrf = await _register(client, f"concurrent-address-{uuid4().hex}@example.test")
    headers = _account_headers(session_cookie, csrf)

    async def add_address(street: str) -> int:
        response = await client.post(
            "/accounts/profile/addresses",
            headers=headers,
            json={
                "label": street,
                "address_type": "address",
                "street": street,
                "building_number": "1",
                "postal_code": "10-001",
                "city": "Olsztyn",
                "country": "PL",
            },
        )
        assert response.status_code == 201, response.text
        return response.status_code

    results = await asyncio.gather(add_address("Pierwsza"), add_address("Druga"))
    assert tuple(results) == (201, 201)
    addresses = await client.get(
        "/accounts/profile/addresses",
        headers={"Cookie": f"sensoria_session={session_cookie}"},
    )
    assert len(addresses.json()["items"]) == 2
    assert sum(item["is_default"] for item in addresses.json()["items"]) == 1

    no_csrf = await client.post(
        "/accounts/profile/addresses",
        headers={"Origin": "http://localhost", "Cookie": f"sensoria_session={session_cookie}"},
        json={
            "label": "Dom",
            "address_type": "address",
            "street": "Długa",
            "building_number": "4",
            "postal_code": "10-001",
            "city": "Olsztyn",
        },
    )
    assert no_csrf.status_code == 403


@pytest.mark.asyncio
async def test_email_change_keeps_old_identity_until_confirmation_and_rotates_session(
    postgres_client: tuple[AsyncClient, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _engine = postgres_client
    session_cookie, csrf = await _register(client, "before@example.test")
    captured: dict[str, str] = {}

    from sensoria.modules.accounts import profile

    real_encrypt = profile._encrypt_mail_payload

    def capture_payload(payload: dict[str, str]) -> str:
        captured.update(payload)
        return real_encrypt(payload)

    monkeypatch.setattr(profile, "_encrypt_mail_payload", capture_payload)
    request = await client.post(
        "/accounts/profile/email-change",
        headers=_account_headers(session_cookie, csrf),
        json={"email": " New.Address+shop@Example.test "},
    )
    assert request.status_code == 200, request.text
    assert captured["to"] == "new.address+shop@example.test"
    assert captured["token"]

    before_confirmation = await client.get(
        "/accounts/profile", headers={"Cookie": f"sensoria_session={session_cookie}"}
    )
    assert before_confirmation.json()["email"] == "before@example.test"
    assert before_confirmation.json()["pending_email"] == "new.address+shop@example.test"

    confirm = await client.post(
        "/accounts/profile/email-change/confirm",
        headers=_account_headers(session_cookie, csrf),
        json={"token": captured["token"]},
    )
    assert confirm.status_code == 200, confirm.text
    rotated = confirm.cookies.get("sensoria_session")
    assert rotated and rotated != session_cookie
    assert confirm.cookies.get("sensoria_csrf")
    changed = await client.get(
        "/accounts/profile", headers={"Cookie": f"sensoria_session={rotated}"}
    )
    assert changed.status_code == 200
    assert changed.json()["email"] == "new.address+shop@example.test"
    assert changed.json()["pending_email"] is None
    old_session = await client.get(
        "/accounts/session", headers={"Cookie": f"sensoria_session={session_cookie}"}
    )
    assert old_session.status_code == 401


@pytest.mark.asyncio
async def test_email_change_rejects_address_owned_by_another_customer(
    postgres_client: tuple[AsyncClient, Any],
) -> None:
    client, _engine = postgres_client
    first_session, _first_csrf = await _register(client, "first@example.test")
    second_session, second_csrf = await _register(client, "taken@example.test")
    response = await client.post(
        "/accounts/profile/email-change",
        headers=_account_headers(second_session, second_csrf),
        json={"email": "first@example.test"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_USED"
    # The endpoint did not alter the other customer's identifier or account data.
    first_profile = await client.get(
        "/accounts/profile", headers={"Cookie": f"sensoria_session={first_session}"}
    )
    assert first_profile.json()["email"] == "first@example.test"


@pytest.mark.asyncio
async def test_email_change_confirmation_works_without_the_requesting_browser_session(
    postgres_client: tuple[AsyncClient, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _engine = postgres_client
    session_cookie, csrf = await _register(client, "cross-device@example.test")
    captured: dict[str, str] = {}

    from sensoria.main import app
    from sensoria.modules.accounts import profile

    real_encrypt = profile._encrypt_mail_payload

    def capture_payload(payload: dict[str, str]) -> str:
        captured.update(payload)
        return real_encrypt(payload)

    monkeypatch.setattr(profile, "_encrypt_mail_payload", capture_payload)
    request = await client.post(
        "/accounts/profile/email-change",
        headers=_account_headers(session_cookie, csrf),
        json={"email": "confirmed-on-phone@example.test"},
    )
    assert request.status_code == 200

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as phone:
        phone_csrf = await _csrf(phone)
        confirmed = await phone.post(
            "/accounts/profile/email-change/confirm",
            headers=_headers(phone_csrf),
            json={"token": captured["token"]},
        )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["session_preserved"] is False
    assert "Zaloguj się nowym adresem" in confirmed.json()["message"]
    assert not confirmed.cookies.get("sensoria_session")

    old = await client.get(
        "/accounts/session", headers={"Cookie": f"sensoria_session={session_cookie}"}
    )
    assert old.status_code == 401
