"""Customer session authentication. Identity always comes from the revocable DB session."""

from __future__ import annotations

import hashlib
import hmac
import re
from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.database import get_session
from sensoria.shared.errors import DomainError

from .clock import utc_now
from .models import AccountSession, Customer

SESSION_COOKIE = "sensoria_session"
CSRF_COOKIE = "sensoria_csrf"
_email_pattern = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def normalize_email(value: str) -> str:
    """Normalize only whitespace and case; preserve plus and dot semantics."""
    normalized = value.strip().lower()
    if len(normalized) > 320 or not _email_pattern.fullmatch(normalized):
        raise DomainError("INVALID_EMAIL", "Podaj prawidłowy adres e-mail.", 422)
    return normalized


def digest_secret(secret: str) -> str:
    """Return a keyed digest so a database leak does not expose session credentials."""
    from sensoria.config import get_settings

    key = get_settings().SECRET_KEY.get_secret_value().encode()
    return hmac.new(key, secret.encode(), hashlib.sha256).hexdigest()


def deleted_email_digest(email: str) -> str:
    """Keyed, non-reversible suppression marker preventing account resurrection."""
    return digest_secret("deleted-email:" + normalize_email(email))


async def require_customer_id(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UUID:
    """Validate session existence, revocation and both expiration limits per request."""
    token = request.cookies.get(SESSION_COOKIE)
    now = utc_now()
    if token:
        account_session = await session.scalar(
            select(AccountSession)
            .join(Customer, Customer.id == AccountSession.customer_id)
            .where(
                Customer.deleted_at.is_(None),
                AccountSession.secret_hash == digest_secret(token),
                AccountSession.revoked_at.is_(None),
                AccountSession.idle_expires_at > now,
                AccountSession.absolute_expires_at > now,
            )
        )
        if account_session is not None:
            request.state.customer_id = account_session.customer_id
            request.state.account_session_id = account_session.id
            request.state.csrf_hash = account_session.csrf_hash
            idle_seconds = 14 * 86400 if account_session.remember_me else 12 * 3600
            account_session.last_seen_at = now
            account_session.idle_expires_at = min(
                now + timedelta(seconds=idle_seconds), account_session.absolute_expires_at
            )
            await session.commit()
            return account_session.customer_id
    raise DomainError(
        "AUTHENTICATION_REQUIRED",
        "Zaloguj się, aby zobaczyć dane swojego konta.",
        401,
        headers={"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"},
    )
