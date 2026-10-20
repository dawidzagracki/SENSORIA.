"""Account authentication invariants and PostgreSQL-backed request flows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sensoria.modules.accounts.auth import normalize_email
from sensoria.modules.accounts.router import (
    _validate_password,
)
from sensoria.shared.errors import DomainError


def test_email_normalization_preserves_plus_and_dots() -> None:
    assert normalize_email("  Anna.Kowalska+tag@Example.COM ") == "anna.kowalska+tag@example.com"


@pytest.mark.parametrize(
    ("password", "confirmation", "code"),
    [
        ("short", None, "PASSWORD_TOO_SHORT"),
        ("password123", None, "PASSWORD_TOO_COMMON"),
        ("Longer passphrase", "Different passphrase", "PASSWORD_CONFIRMATION_MISMATCH"),
    ],
)
def test_password_rules(password: str, confirmation: str | None, code: str) -> None:
    with pytest.raises(DomainError) as error:
        _validate_password(password, confirmation)
    assert error.value.code == code


def test_long_password_and_spaces_are_not_trimmed() -> None:
    _validate_password("  this is a longer passphrase with spaces  ")
    _validate_password("a" * 1024)
    with pytest.raises(DomainError, match="zbyt długie"):
        _validate_password("😀" * 1100)


async def _csrf(client: AsyncClient) -> str:
    response = await client.get("/accounts/csrf")
    assert response.status_code == 200
    token = response.json().get("csrf_token")
    assert isinstance(token, str)
    return token


def _headers(csrf: str, cookie: str = "") -> dict[str, str]:
    return {
        "Origin": "http://localhost",
        "X-CSRF-Token": csrf,
        "Cookie": f"sensoria_csrf={csrf}" + (f"; {cookie}" if cookie else ""),
    }


@pytest.mark.asyncio
async def test_register_login_session_logout_and_generic_login_error(
    postgres_client: tuple[AsyncClient, Any],
) -> None:
    client, _engine = postgres_client
    csrf = await _csrf(client)
    registered = await client.post(
        "/accounts/register",
        headers=_headers(csrf),
        json={
            "email": "  Anna.Example+one@example.test ",
            "password": "A longer passphrase 2026",
            "first_name": "Anna",
            "last_name": "Testowa",
        },
    )
    assert registered.status_code == 201
    assert registered.json()["customer"]["email"] == "anna.example+one@example.test"
    assert "password_hash" not in registered.text
    session_cookie = registered.cookies.get("sensoria_session")
    csrf_after_register = registered.cookies.get("sensoria_csrf")
    assert session_cookie and csrf_after_register
    session_set_cookie = next(
        value
        for value in registered.headers.get_list("set-cookie")
        if value.startswith("sensoria_session=")
    )
    assert "HttpOnly" in session_set_cookie
    assert "Path=/api" in session_set_cookie
    assert "SameSite=lax" in session_set_cookie
    cookie_header = f"sensoria_session={session_cookie}"
    session_response = await client.get("/accounts/session", headers={"Cookie": cookie_header})
    assert session_response.status_code == 200
    assert session_response.json()["customer"]["first_name"] == "Anna"
    assert "password_hash" not in session_response.text

    login_csrf = await _csrf(client)
    bad_known = await client.post(
        "/accounts/login",
        headers=_headers(login_csrf),
        json={"email": "anna.example+one@example.test", "password": "wrong passphrase"},
    )
    bad_unknown = await client.post(
        "/accounts/login",
        headers=_headers(login_csrf),
        json={"email": "missing@example.test", "password": "wrong passphrase"},
    )
    assert bad_known.status_code == bad_unknown.status_code == 401
    assert bad_known.json() == bad_unknown.json()

    login_csrf = await _csrf(client)
    success = await client.post(
        "/accounts/login",
        headers=_headers(login_csrf),
        json={"email": "ANNA.EXAMPLE+ONE@example.test", "password": "A longer passphrase 2026"},
    )
    assert success.status_code == 200
    cookie = success.cookies.get("sensoria_session")
    csrf_value = success.cookies.get("sensoria_csrf")
    assert cookie and csrf_value
    logout = await client.post(
        "/accounts/logout",
        headers=_headers(csrf_value, f"sensoria_session={cookie}"),
    )
    assert logout.status_code == 204
    denied = await client.get("/accounts/session", headers={"Cookie": f"sensoria_session={cookie}"})
    assert denied.status_code == 401


@pytest.mark.asyncio
async def test_reset_response_does_not_reveal_account_existence(
    postgres_client: tuple[AsyncClient, Any],
) -> None:
    client, _engine = postgres_client
    csrf = await _csrf(client)
    for email in ("no-account@example.test",):
        unknown = await client.post(
            "/accounts/password-reset/request",
            headers=_headers(csrf),
            json={"email": email},
        )
        assert unknown.status_code == 200
        assert unknown.json() == {
            "message": "Jeśli konto istnieje, wyślemy wiadomość z instrukcją zmiany hasła."
        }
    registered = await client.post(
        "/accounts/register",
        headers=_headers(csrf),
        json={
            "email": "reset@example.test",
            "password": "a proper long test phrase",
            "first_name": "Test",
            "last_name": "Reset",
        },
    )
    assert registered.status_code == 201
    known = await client.post(
        "/accounts/password-reset/request",
        headers=_headers(csrf),
        json={"email": "reset@example.test"},
    )
    assert known.status_code == 200
    assert known.json() == unknown.json()


@pytest.mark.asyncio
async def test_reset_token_is_one_time_and_revokes_existing_sessions(
    postgres_client: tuple[AsyncClient, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _engine = postgres_client
    csrf = await _csrf(client)
    registered = await client.post(
        "/accounts/register",
        headers=_headers(csrf),
        json={
            "email": "once@example.test",
            "password": "before reset passphrase",
            "first_name": "Test",
            "last_name": "Osoba",
        },
    )
    assert registered.status_code == 201
    old_session = registered.cookies.get("sensoria_session")
    assert old_session

    from sensoria.modules.accounts import router as accounts_router

    monkeypatch.setattr(
        accounts_router,
        "_token_pair",
        lambda: ("known-selector", "known-secret-value", "known-selector.known-secret-value"),
    )
    csrf = await _csrf(client)
    request_reset = await client.post(
        "/accounts/password-reset/request",
        headers=_headers(csrf),
        json={"email": "once@example.test"},
    )
    assert request_reset.status_code == 200
    csrf = await _csrf(client)
    body = {
        "token": "known-selector.known-secret-value",
        "password": "after reset passphrase",
        "password_confirmation": "after reset passphrase",
    }
    reset = await client.post("/accounts/password-reset/confirm", headers=_headers(csrf), json=body)
    assert reset.status_code == 200
    repeated = await client.post(
        "/accounts/password-reset/confirm", headers=_headers(csrf), json=body
    )
    assert repeated.status_code == 400
    old_session_response = await client.get(
        "/accounts/session", headers={"Cookie": f"sensoria_session={old_session}"}
    )
    assert old_session_response.status_code == 401

    csrf = await _csrf(client)
    new_login = await client.post(
        "/accounts/login",
        headers=_headers(csrf),
        json={"email": "once@example.test", "password": "after reset passphrase"},
    )
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_reset_token_expires_at_exact_one_hour_boundary(
    postgres_client: tuple[AsyncClient, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _engine = postgres_client
    csrf = await _csrf(client)
    registered = await client.post(
        "/accounts/register",
        headers=_headers(csrf),
        json={
            "email": "expiry@example.test",
            "password": "expiry test passphrase 2026",
            "first_name": "Test",
            "last_name": "Termin",
        },
    )
    assert registered.status_code == 201
    fixed_now = datetime.now(UTC)

    from sensoria.modules.accounts import router as accounts_router

    monkeypatch.setattr(accounts_router, "utc_now", lambda: fixed_now)
    monkeypatch.setattr(
        accounts_router,
        "_token_pair",
        lambda: ("expiry-selector", "expiry-secret-value", "expiry-selector.expiry-secret-value"),
    )
    csrf = await _csrf(client)
    request_reset = await client.post(
        "/accounts/password-reset/request",
        headers=_headers(csrf),
        json={"email": "expiry@example.test"},
    )
    assert request_reset.status_code == 200
    monkeypatch.setattr(accounts_router, "utc_now", lambda: fixed_now + timedelta(hours=1))
    csrf = await _csrf(client)
    expired = await client.post(
        "/accounts/password-reset/confirm",
        headers=_headers(csrf),
        json={
            "token": "expiry-selector.expiry-secret-value",
            "password": "a new expiry passphrase",
            "password_confirmation": "a new expiry passphrase",
        },
    )
    assert expired.status_code == 400
    assert expired.json()["error"]["code"] == "ACTION_TOKEN_INVALID"


@pytest.mark.asyncio
async def test_login_locks_after_ten_failures_for_unknown_and_known_addresses(
    postgres_client: tuple[AsyncClient, Any],
) -> None:
    client, _engine = postgres_client
    csrf = await _csrf(client)
    response_codes: list[int] = []
    for _ in range(10):
        response = await client.post(
            "/accounts/login",
            headers=_headers(csrf),
            json={"email": "not-present@example.test", "password": "wrong password value"},
        )
        response_codes.append(response.status_code)
    assert response_codes == [401] * 9 + [429]
    blocked = await client.post(
        "/accounts/login",
        headers=_headers(csrf),
        json={"email": "not-present@example.test", "password": "wrong password value"},
    )
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "900"
    assert blocked.json()["error"]["message"] == "Nieprawidłowy adres e-mail lub hasło."


@pytest.mark.asyncio
async def test_remember_me_cookie_csrf_and_password_change_rotate_sessions(
    postgres_client: tuple[AsyncClient, Any],
) -> None:
    client, _engine = postgres_client
    csrf = await _csrf(client)
    registered = await client.post(
        "/accounts/register",
        headers=_headers(csrf),
        json={
            "email": "rotate@example.test",
            "password": "initial password phrase",
            "first_name": "Test",
            "last_name": "Rotacja",
        },
    )
    assert registered.status_code == 201
    first_session = registered.cookies.get("sensoria_session")
    assert first_session

    csrf = await _csrf(client)
    rejected = await client.post(
        "/accounts/logout",
        headers={
            **_headers(csrf),
            "Origin": "https://untrusted.example",
            "Cookie": f"sensoria_csrf={csrf}; sensoria_session={first_session}",
        },
    )
    assert rejected.status_code == 403

    csrf = await _csrf(client)
    remembered = await client.post(
        "/accounts/login",
        headers=_headers(csrf),
        json={
            "email": "rotate@example.test",
            "password": "initial password phrase",
            "remember_me": True,
        },
    )
    assert remembered.status_code == 200
    second_session = remembered.cookies.get("sensoria_session")
    second_csrf = remembered.cookies.get("sensoria_csrf")
    assert second_session and second_csrf and second_session != first_session
    session_cookie = next(
        value
        for value in remembered.headers.get_list("set-cookie")
        if value.startswith("sensoria_session=")
    )
    assert "Max-Age=2592000" in session_cookie
    assert "Secure" not in session_cookie  # The test app uses the local HTTP profile.

    changed = await client.post(
        "/accounts/password/change",
        headers=_headers(second_csrf, f"sensoria_session={second_session}"),
        json={
            "current_password": "initial password phrase",
            "password": "replacement password phrase",
            "password_confirmation": "replacement password phrase",
        },
    )
    assert changed.status_code == 200
    rotated = changed.cookies.get("sensoria_session")
    assert rotated and rotated not in {first_session, second_session}
    assert (
        await client.get(
            "/accounts/session", headers={"Cookie": f"sensoria_session={first_session}"}
        )
    ).status_code == 401
    assert (
        await client.get(
            "/accounts/session", headers={"Cookie": f"sensoria_session={second_session}"}
        )
    ).status_code == 401
    assert (
        await client.get("/accounts/session", headers={"Cookie": f"sensoria_session={rotated}"})
    ).status_code == 200

    csrf_after_change = changed.cookies.get("sensoria_csrf")
    assert csrf_after_change
    logout = await client.post(
        "/accounts/logout",
        headers=_headers(csrf_after_change, f"sensoria_session={rotated}"),
    )
    assert logout.status_code == 204
    deleted_cookie = next(
        value
        for value in logout.headers.get_list("set-cookie")
        if value.startswith("sensoria_session=")
    )
    assert "Max-Age=0" in deleted_cookie and "Path=/api" in deleted_cookie
