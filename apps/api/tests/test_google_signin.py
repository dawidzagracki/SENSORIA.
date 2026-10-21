"""Sign in with Google: state check, verified e-mail requirement, account creation and reuse."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from pydantic import SecretStr
from sensoria.config import Settings, get_settings
from sensoria.modules.accounts import oauth
from sensoria.modules.accounts.models import Customer
from sqlalchemy import func, select

from . import test_cart
from .test_cart import CartEnvironment

cart_environment = test_cart.cart_environment
__all__ = ["cart_environment"]


@pytest.fixture
def google(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    configured: Settings = get_settings().model_copy(
        update={
            "GOOGLE_CLIENT_ID": "client",
            "GOOGLE_CLIENT_SECRET": SecretStr("secret"),
            "SITE_URL": "http://localhost",
        }
    )
    monkeypatch.setattr(oauth, "get_settings", lambda: configured)
    profile: dict[str, Any] = {
        "email": "Nowa.Klientka@Example.com",
        "email_verified": True,
        "given_name": "Nowa",
        "family_name": "Klientka",
    }
    monkeypatch.setattr(oauth, "_post_form", lambda *a, **k: {"access_token": "token"})
    monkeypatch.setattr(oauth, "_get_json", lambda *a, **k: profile)
    return profile


async def _start(client: Any) -> tuple[str, str]:
    response = await client.get("/auth/google/start?next=/konto/biblioteka", follow_redirects=False)
    assert response.status_code == 302
    state = parse_qs(urlsplit(response.headers["location"]).query)["state"][0]
    return state, response.cookies["sensoria_oauth_state"]


@pytest.mark.asyncio
async def test_providers_reflect_configuration(
    cart_environment: CartEnvironment, google: dict[str, Any]
) -> None:
    client, _ = cart_environment
    assert (await client.get("/accounts/oauth/providers")).json() == {"google": True}


@pytest.mark.asyncio
async def test_first_sign_in_creates_a_verified_customer_and_a_session(
    cart_environment: CartEnvironment, google: dict[str, Any]
) -> None:
    client, factory = cart_environment
    state, cookie = await _start(client)
    done = await client.get(
        f"/auth/google/callback?code=abc&state={state}",
        cookies={"sensoria_oauth_state": cookie},
        follow_redirects=False,
    )
    assert done.status_code == 302
    assert done.headers["location"] == "/konto/biblioteka"
    assert "sensoria_session" in done.cookies
    async with factory() as session:
        customer = await session.scalar(
            select(Customer).where(Customer.email == "nowa.klientka@example.com")
        )
        assert customer is not None and customer.email_verified_at is not None
        assert (customer.first_name, customer.last_name) == ("Nowa", "Klientka")

    again_state, again_cookie = await _start(client)
    await client.get(
        f"/auth/google/callback?code=abc&state={again_state}",
        cookies={"sensoria_oauth_state": again_cookie},
        follow_redirects=False,
    )
    async with factory() as session:
        count = await session.scalar(select(func.count()).select_from(Customer))
        assert count == 1


@pytest.mark.asyncio
async def test_wrong_state_or_unverified_email_is_refused(
    cart_environment: CartEnvironment, google: dict[str, Any]
) -> None:
    client, factory = cart_environment
    _state, cookie = await _start(client)
    wrong = await client.get(
        "/auth/google/callback?code=abc&state=forged",
        cookies={"sensoria_oauth_state": cookie},
        follow_redirects=False,
    )
    assert wrong.headers["location"] == "/konto?google=error"
    google["email_verified"] = False
    state, cookie = await _start(client)
    unverified = await client.get(
        f"/auth/google/callback?code=abc&state={state}",
        cookies={"sensoria_oauth_state": cookie},
        follow_redirects=False,
    )
    assert unverified.headers["location"] == "/konto?google=error"
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(Customer)) == 0
