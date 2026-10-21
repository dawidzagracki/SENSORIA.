"""Sign in with Google (OAuth 2.0 authorization code flow).

The shop never sees a Google password. A Google account whose e-mail Google itself reports as
verified proves ownership of that address, so it signs in (or creates) the customer with that
address and lets previously guest-bought purchases attach, exactly like a confirmed e-mail link.
"""

from __future__ import annotations

import asyncio
import json
import secrets
from datetime import UTC, datetime
from typing import Annotated, Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as HttpRequest
from urllib.request import urlopen

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.config import Settings, get_settings
from sensoria.database import get_session
from sensoria.shared.errors import DomainError

from .auth import CSRF_COOKIE, SESSION_COOKIE
from .models import Customer
from .purchase_linking import reconcile_guest_purchases
from .router import _audit, _new_session, _secure_cookie, hasher, safe_login_return_path

google_router = APIRouter(tags=["google-sign-in"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
STATE_COOKIE = "sensoria_oauth_state"
FAILED = "/konto?google=error"


def google_enabled(settings: Settings) -> bool:
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)


def _redirect_uri(settings: Settings) -> str:
    return f"{(settings.SITE_URL or '').rstrip('/')}/api/auth/google/callback"


def _post_form(url: str, form: dict[str, str], timeout: float) -> dict[str, Any]:
    request = HttpRequest(  # noqa: S310 - endpoint is operator configuration
        url,
        data=urlencode(form).encode(),
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        payload = json.loads(response.read(200_000))
    return payload if isinstance(payload, dict) else {}


def _get_json(url: str, bearer: str, timeout: float) -> dict[str, Any]:
    request = HttpRequest(url, headers={"Authorization": f"Bearer {bearer}"})  # noqa: S310
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        payload = json.loads(response.read(200_000))
    return payload if isinstance(payload, dict) else {}


@google_router.get("/accounts/oauth/providers")
async def providers() -> dict[str, bool]:
    return {"google": google_enabled(get_settings())}


@google_router.get("/auth/google/start")
async def start(next: Annotated[str | None, Query(max_length=300)] = None) -> RedirectResponse:
    settings = get_settings()
    if not google_enabled(settings):
        raise DomainError("GOOGLE_NOT_CONFIGURED", "Logowanie przez Google jest niedostępne.", 404)
    nonce = secrets.token_urlsafe(24)
    return_to = safe_login_return_path(next)
    query = urlencode(
        {
            "client_id": settings.GOOGLE_CLIENT_ID or "",
            "redirect_uri": _redirect_uri(settings),
            "response_type": "code",
            "scope": "openid email profile",
            "state": nonce,
            "prompt": "select_account",
        }
    )
    response = RedirectResponse(f"{settings.GOOGLE_AUTH_URL}?{query}", status_code=302)
    response.set_cookie(
        STATE_COOKIE,
        f"{nonce}|{return_to}",
        max_age=600,
        path="/api/auth/google",
        secure=settings.ENVIRONMENT == "production",
        httponly=True,
        samesite="lax",
    )
    return response


@google_router.get("/auth/google/callback")
async def callback(
    request: Request,
    session: SessionDependency,
    code: Annotated[str | None, Query(max_length=2048)] = None,
    state: Annotated[str | None, Query(max_length=256)] = None,
) -> RedirectResponse:
    settings = get_settings()
    stored = request.cookies.get(STATE_COOKIE, "")
    nonce, _, return_to = stored.partition("|")
    if not google_enabled(settings) or not code or not state or not nonce:
        return RedirectResponse(FAILED, status_code=302)
    if not secrets.compare_digest(nonce, state):
        return RedirectResponse(FAILED, status_code=302)
    secret = settings.GOOGLE_CLIENT_SECRET
    assert secret is not None
    try:
        token = await asyncio.to_thread(
            _post_form,
            settings.GOOGLE_TOKEN_URL,
            {
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID or "",
                "client_secret": secret.get_secret_value(),
                "redirect_uri": _redirect_uri(settings),
                "grant_type": "authorization_code",
            },
            10.0,
        )
        access = token.get("access_token")
        if not isinstance(access, str):
            return RedirectResponse(FAILED, status_code=302)
        profile = await asyncio.to_thread(_get_json, settings.GOOGLE_USERINFO_URL, access, 10.0)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        return RedirectResponse(FAILED, status_code=302)
    email = profile.get("email")
    if not isinstance(email, str) or profile.get("email_verified") is not True:
        return RedirectResponse(FAILED, status_code=302)
    email = email.strip().lower()
    now = datetime.now(UTC)
    customer = await session.scalar(
        select(Customer).where(Customer.email == email).with_for_update()
    )
    if customer is not None and customer.deleted_at is not None:
        return RedirectResponse(FAILED, status_code=302)
    if customer is None:
        given = str(profile.get("given_name") or "").strip()[:100]
        family = str(profile.get("family_name") or "").strip()[:100]
        fallback = str(profile.get("name") or email.split("@")[0]).strip()
        customer = Customer(
            email=email,
            # Unusable random password: sign-in is through Google; a reset mail can set a real one.
            password_hash=hasher.hash(secrets.token_urlsafe(48)),
            first_name=given or fallback[:100] or "Klientka",
            last_name=family or "—",
            email_verified_at=now,
        )
        session.add(customer)
        await session.flush()
        session.add(_audit(customer.id, "registered", customer.id, {"provider": "google"}))
    elif customer.email_verified_at is None:
        customer.email_verified_at = now
    customer.last_login_at = now
    raw, csrf, max_age = await _new_session(session, customer, True, now)
    await reconcile_guest_purchases(session, customer.id, source="oauth", at=now)
    session.add(_audit(customer.id, "login_succeeded", customer.id, {"provider": "google"}))
    await session.commit()
    response = RedirectResponse(safe_login_return_path(return_to or None), status_code=302)
    _secure_cookie(response, SESSION_COOKIE, raw, max_age)
    _secure_cookie(response, CSRF_COOKIE, csrf, 86400)
    response.delete_cookie(STATE_COOKIE, path="/api/auth/google")
    response.headers["Cache-Control"] = "private, no-store"
    return response
