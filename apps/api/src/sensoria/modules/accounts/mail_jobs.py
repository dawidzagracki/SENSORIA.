"""Helpers for a future [63] worker consuming account email intents."""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
from typing import Any
from urllib.parse import quote
from uuid import UUID

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sensoria.config import get_settings
from sensoria.database import SessionFactory
from sensoria.modules.accounts.auth import digest_secret
from sensoria.modules.accounts.clock import utc_now
from sensoria.modules.accounts.models import (
    AccountActionToken,
    AuthEmailJob,
    Customer,
    LoginLink,
)


def decrypt_auth_email_payload(ciphertext: str) -> dict[str, str]:
    """Decrypt a durable job payload only inside a trusted email worker."""
    key = hashlib.sha256(
        get_settings().SECRET_KEY.get_secret_value().encode() + b"sensoria-auth-mail-v1"
    ).digest()
    packed = base64.urlsafe_b64decode(ciphertext.encode())
    cleartext = AESGCM(key).decrypt(packed[:12], packed[12:], b"auth-email-v1")
    value: Any = json.loads(cleartext)
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("to"), str)
        or not isinstance(value.get("token"), str)
    ):
        raise ValueError("Nieprawidłowy zaszyfrowany ładunek wiadomości konta.")
    return value


def build_auth_email_link(purpose: str, token: str, configured_origin: str | None) -> str:
    """Build a path-token link from the configured origin, never an incoming Host."""
    if purpose not in {"password_reset", "email_verification", "login_link", "email_change"}:
        raise ValueError("Nieznany rodzaj wiadomości konta.")
    if not configured_origin:
        raise ValueError("Brak skonfigurowanego adresu publicznego aplikacji.")
    route = {
        "password_reset": "konto/ustaw-haslo",
        "email_verification": "konto/potwierdz-email",
        "login_link": "konto/link-logowania",
        "email_change": "konto/potwierdz-email-zmiane",
    }[purpose]
    if purpose == "email_change":
        # Keep the bearer secret out of proxy path logs and HTTP referrers.
        return f"{configured_origin}/{route}#{quote(token, safe='')}"
    return f"{configured_origin}/{route}/{quote(token, safe='')}"


async def login_link_job_is_current(session: AsyncSession, job_id: UUID, token: str) -> bool:
    """Recheck before provider dispatch so invalidated or expired links are not emailed."""
    job = await session.get(AuthEmailJob, job_id)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    if job is None or job.purpose != "login_link" or job.status not in {"pending", "queued"}:
        return False
    link = await session.scalar(
        select(LoginLink).where(
            LoginLink.email_job_id == job.id,
            LoginLink.token_hash == token_hash,
            LoginLink.used_at.is_(None),
            LoginLink.invalidated_at.is_(None),
            LoginLink.expires_at > utc_now(),
        )
    )
    return link is not None and hmac.compare_digest(link.token_hash, token_hash)


async def email_change_job_is_current(session: AsyncSession, job_id: UUID, token: str) -> bool:
    """Recheck the pending address and one-time token immediately before dispatch."""
    job = await session.get(AuthEmailJob, job_id)
    try:
        selector, secret = token.split(".", 1)
    except ValueError:
        return False
    if job is None or job.purpose != "email_change" or job.status not in {"pending", "queued"}:
        return False
    action = await session.scalar(
        select(AccountActionToken)
        .join(Customer, Customer.id == AccountActionToken.customer_id)
        .where(
            AccountActionToken.selector == selector,
            AccountActionToken.purpose == "email_change",
            AccountActionToken.customer_id == job.customer_id,
            AccountActionToken.consumed_at.is_(None),
            AccountActionToken.expires_at > utc_now(),
            AccountActionToken.target_email == Customer.pending_email,
        )
    )
    return action is not None and hmac.compare_digest(action.secret_hash, digest_secret(secret))


def email_change_content(link: str) -> tuple[str, str, str]:
    """Return the new-address ownership confirmation copy without profile data."""
    subject = "Potwierdź nowy adres e-mail SENSORIA"
    plain = (
        "Aby zmienić adres e-mail na koncie SENSORIA, potwierdź nowy adres: "
        f"{link}\n\nLink jest ważny przez 24 godziny i można użyć go tylko raz."
    )
    safe_link = html.escape(link, quote=True)
    body = (
        "<p>Potwierdź nowy adres e-mail na swoim koncie SENSORIA.</p>"
        f'<p><a href="{safe_link}">Potwierdź adres e-mail</a></p>'
        "<p>Link jest ważny przez 24 godziny i można użyć go tylko raz.</p>"
    )
    return subject, body, plain


def login_link_email_content(link: str) -> tuple[str, str, str]:
    """Provide HTML/text content contract until the reusable [62] renderer exists."""
    subject = "Zaloguj się do SENSORIA"
    text = (
        "Kliknij przycisk logowania, aby zalogować się do swojego konta SENSORIA.\n\n"
        f"Zaloguj się: {link}\n\n"
        "Link jest jednorazowy i ważny przez 15 minut.\n"
        "Jeśli nie prosiłaś o ten link, zignoruj tę wiadomość."
    )
    safe_link = html.escape(link, quote=True)
    html_body = (
        "<p>Zaloguj się do swojego konta SENSORIA.</p>"
        f'<p><a href="{safe_link}">Zaloguj się</a></p>'
        "<p>Link jest jednorazowy i ważny przez 15 minut.</p>"
        "<p>Jeśli nie prosiłaś o ten link, zignoruj tę wiadomość.</p>"
    )
    return subject, html_body, text


async def cleanup_login_link_payloads(
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
    *,
    batch_size: int = 500,
) -> int:
    """Erase encrypted bearer payloads after dispatch/cancellation or link expiry."""
    if batch_size < 1:
        raise ValueError("batch_size musi być dodatnie.")
    now = utc_now()
    async with session_factory() as session, session.begin():
        jobs = list(
            (
                await session.scalars(
                    select(AuthEmailJob)
                    .outerjoin(LoginLink, LoginLink.email_job_id == AuthEmailJob.id)
                    .outerjoin(
                        AccountActionToken,
                        (AccountActionToken.customer_id == AuthEmailJob.customer_id)
                        & (AuthEmailJob.purpose == AccountActionToken.purpose)
                        & (
                            AuthEmailJob.idempotency_key
                            == func.concat(
                                AccountActionToken.purpose, ":", AccountActionToken.selector
                            )
                        ),
                    )
                    .where(
                        AuthEmailJob.purpose.in_(("login_link", "email_change")),
                        AuthEmailJob.payload_ciphertext != "",
                        or_(
                            AuthEmailJob.status.in_(("sent", "cancelled")),
                            LoginLink.expires_at <= now,
                            AccountActionToken.consumed_at.is_not(None),
                            AccountActionToken.expires_at <= now,
                        ),
                    )
                    .order_by(AuthEmailJob.created_at, AuthEmailJob.id)
                    .limit(batch_size)
                    .with_for_update(of=AuthEmailJob, skip_locked=True)
                )
            ).all()
        )
        for job in jobs:
            if job.status not in {"sent", "cancelled"}:
                job.status = "cancelled"
                job.failure_code = "link_expired"
            job.payload_ciphertext = ""
        return len(jobs)
