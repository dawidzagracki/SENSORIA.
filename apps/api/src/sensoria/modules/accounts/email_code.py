"""Sign in with a one-time code sent by e-mail.

Whoever can read the mailbox of a purchase proves the purchase is theirs, so the code opens a
passwordless customer session: guest purchases attach to it exactly like after a confirmed link.
The request endpoint never reveals whether the address has any purchases.
"""

from __future__ import annotations

import hmac
import secrets
from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.config import get_settings
from sensoria.database import get_session
from sensoria.modules.mail.outbox import enqueue_mail
from sensoria.modules.orders.models import Order
from sensoria.shared.errors import DomainError

from .auth import CSRF_COOKIE, SESSION_COOKIE, digest_secret, normalize_email
from .clock import utc_now
from .models import Customer, EmailLoginCode
from .purchase_linking import reconcile_guest_purchases
from .router import (
    _audit,
    _client_ip,
    _key_hash,
    _new_session,
    _require_csrf,
    _secure_cookie,
    hasher,
    safe_login_return_path,
)

email_code_router = APIRouter(prefix="/auth/email-code", tags=["email-code-login"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]

CODE_TTL = timedelta(minutes=10)
MAX_ATTEMPTS = 5
MESSAGE = "Jeśli ten adres ma w sklepie zakupy, wysłaliśmy na niego kod. Jest ważny 10 minut."
_PRIVATE = {"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"}


class CodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=320)


class CodeVerify(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=320)
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    return_to: str | None = Field(default=None, max_length=2048)


def _digest(email: str, code: str) -> str:
    return digest_secret(f"email-code:{email}:{code}")


@email_code_router.post("/request")
async def request_code(
    payload: CodeRequest,
    request: Request,
    response: Response,
    session: SessionDependency,
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    await _require_csrf(request, session, x_csrf_token)
    response.headers.update(_PRIVATE)
    email = normalize_email(payload.email)
    now = utc_now()
    ip_hash = _key_hash("email-code-ip:" + _client_ip(request))
    since = now - timedelta(hours=1)
    by_email = int(
        await session.scalar(
            select(func.count())
            .select_from(EmailLoginCode)
            .where(EmailLoginCode.email == email, EmailLoginCode.created_at > since)
        )
        or 0
    )
    by_ip = int(
        await session.scalar(
            select(func.count())
            .select_from(EmailLoginCode)
            .where(EmailLoginCode.requested_ip == ip_hash, EmailLoginCode.created_at > since)
        )
        or 0
    )
    settings = get_settings()
    if by_email >= settings.EMAIL_CODE_EMAIL_LIMIT or by_ip >= settings.EMAIL_CODE_IP_LIMIT:
        raise DomainError(
            "EMAIL_CODE_RATE_LIMITED",
            "Za dużo prób. Spróbuj ponownie za godzinę.",
            429,
            headers={**_PRIVATE, "Retry-After": "3600"},
        )
    has_purchases = bool(
        await session.scalar(
            select(Order.id)
            .where(func.lower(Order.email) == email, Order.status == "paid")
            .limit(1)
        )
    ) or bool(
        await session.scalar(
            select(Customer.id).where(Customer.email == email, Customer.deleted_at.is_(None))
        )
    )
    # Always record the request so probing an address costs the same either way.
    code = f"{secrets.randbelow(1_000_000):06d}"
    row = EmailLoginCode(
        email=email,
        code_hash=_digest(email, code),
        expires_at=now + CODE_TTL,
        requested_ip=ip_hash,
    )
    if has_purchases:
        await session.execute(
            update(EmailLoginCode)
            .where(EmailLoginCode.email == email, EmailLoginCode.used_at.is_(None))
            .values(used_at=now)
        )
        session.add(row)
        await session.flush()
        await enqueue_mail(
            session,
            template_key="email_code",
            recipient=email,
            variables={"code": code},
            idempotency_key=f"email_code:{row.id}",
        )
    else:
        row.used_at = now
        session.add(row)
    await session.commit()
    return {"message": MESSAGE}


@email_code_router.post("/verify")
async def verify_code(
    payload: CodeVerify,
    request: Request,
    response: Response,
    session: SessionDependency,
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    await _require_csrf(request, session, x_csrf_token)
    response.headers.update(_PRIVATE)
    email = normalize_email(payload.email)
    now = utc_now()
    invalid = DomainError(
        "EMAIL_CODE_INVALID", "Kod jest nieprawidłowy lub wygasł. Poproś o nowy.", 400, _PRIVATE
    )
    row = await session.scalar(
        select(EmailLoginCode)
        .where(
            EmailLoginCode.email == email,
            EmailLoginCode.used_at.is_(None),
            EmailLoginCode.expires_at > now,
        )
        .order_by(EmailLoginCode.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    if row is None or row.attempts >= MAX_ATTEMPTS:
        raise invalid
    if not hmac.compare_digest(row.code_hash, _digest(email, payload.code)):
        row.attempts += 1
        if row.attempts >= MAX_ATTEMPTS:
            row.used_at = now
        await session.commit()
        raise invalid
    row.used_at = now
    customer = await session.scalar(
        select(Customer).where(Customer.email == email).with_for_update()
    )
    if customer is not None and customer.deleted_at is not None:
        await session.commit()
        raise invalid
    if customer is None:
        last = await session.scalar(
            select(Order)
            .where(func.lower(Order.email) == email)
            .order_by(Order.created_at.desc())
            .limit(1)
        )
        shipping = last.shipping_data if last and isinstance(last.shipping_data, dict) else {}
        customer = Customer(
            email=email,
            # Unusable random password: access is by e-mail code; a reset mail can set a real one.
            password_hash=hasher.hash(secrets.token_urlsafe(48)),
            first_name=str(shipping.get("first_name") or "Klient")[:100],
            last_name=str(shipping.get("last_name") or "—")[:100],
            email_verified_at=now,
        )
        session.add(customer)
        await session.flush()
        session.add(_audit(customer.id, "registered", customer.id, {"provider": "email_code"}))
    elif customer.email_verified_at is None:
        customer.email_verified_at = now
    customer.last_login_at = now
    raw, csrf, max_age = await _new_session(session, customer, True, now)
    await reconcile_guest_purchases(session, customer.id, source="email_code", at=now)
    session.add(_audit(customer.id, "login_succeeded", customer.id, {"provider": "email_code"}))
    await session.commit()
    _secure_cookie(response, SESSION_COOKIE, raw, max_age)
    _secure_cookie(response, CSRF_COOKIE, csrf, 86400)
    return {
        "return_to": safe_login_return_path(payload.return_to or "/konto/biblioteka"),
        "customer": {"email": email, "first_name": customer.first_name},
    }
