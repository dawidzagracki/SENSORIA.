"""Registration, password authentication, revocable sessions and recovery API."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import json
import secrets
import time
from datetime import datetime, timedelta
from typing import Annotated, Any
from urllib.parse import unquote, urlsplit
from uuid import UUID, uuid4

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from sensoria.config import get_settings
from sensoria.database import get_session
from sensoria.shared.audit_log import ActorType, AuditLog
from sensoria.shared.errors import DomainError

from .auth import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    deleted_email_digest,
    digest_secret,
    normalize_email,
    require_customer_id,
)
from .clock import utc_now
from .models import (
    AccountActionToken,
    AccountSession,
    AuthAttempt,
    AuthEmailJob,
    Customer,
    DeletedEmailSuppression,
    LoginLink,
)
from .orders import router as account_orders_router
from .privacy import router as account_privacy_router
from .profile import router as account_profile_router
from .purchase_linking import reconcile_guest_purchases
from .shipments import router as account_shipments_router
from .vouchers import router as account_vouchers_router

router = APIRouter(prefix="/accounts", tags=["accounts"])
auth_router = APIRouter(prefix="/auth", tags=["passwordless-auth"])
router.include_router(account_vouchers_router)
router.include_router(account_shipments_router)
router.include_router(account_orders_router)
router.include_router(account_profile_router)
router.include_router(account_privacy_router)
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
CustomerDependency = Annotated[UUID, Depends(require_customer_id)]
hasher = PasswordHasher(
    type=Type.ID, time_cost=2, memory_cost=19_456, parallelism=1, hash_len=32, salt_len=16
)
_dummy_password_hash = hasher.hash("sensoria-dummy-account-password")
_popular_passwords = {
    "1234567890",
    "password123",
    "qwerty1234",
    "zaq12wsx",
    "admin12345",
    "12345678",
    "password",
    "iloveyou",
    "qwertyuiop",
    "polska123",
    "123456789",
    "password1",
    "password12",
    "zaq1@wsx",
    "qwerty123",
    "qwerty12345",
    "adminadmin",
    "letmein123",
    "welcome123",
    "abc1234567",
    "monkey123",
    "dragon123",
    "trustno1",
    "sunshine1",
    "football1",
    "master123",
    "changeme123",
    "hello12345",
    "admin123",
}
_GENERIC_LOGIN_ERROR = "Nieprawidłowy adres e-mail lub hasło."
_RESET_MESSAGE = "Jeśli konto istnieje, wyślemy wiadomość z instrukcją zmiany hasła."
_LOGIN_LINK_MESSAGE = "Jeśli konto istnieje, wyślemy wiadomość z linkiem do logowania."
_LOGIN_LINK_INVALID_MESSAGE = (
    "Ten link jest nieprawidłowy, wygasł lub został już użyty. Poproś o nowy link."
)
_PRIVATE_HEADERS = {"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"}


class RegisterInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=40)


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)
    remember_me: bool = False


class EmailInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=320)


class PasswordInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=20, max_length=100)
    password: str = Field(min_length=1, max_length=1024)
    password_confirmation: str = Field(min_length=1, max_length=1024)


class ChangePasswordInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=1024)
    password: str = Field(min_length=1, max_length=1024)
    password_confirmation: str = Field(min_length=1, max_length=1024)


class LoginLinkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=320)
    return_to: str | None = Field(default=None, max_length=2048)


def safe_login_return_path(value: str | None) -> str:
    """Accept a local path only, including protection against encoded open redirects."""
    fallback = "/konto"
    if not value:
        return fallback
    candidate = value
    for _ in range(3):
        if (
            not candidate.startswith("/")
            or candidate.startswith("//")
            or "\\" in candidate
            or any(ord(character) < 32 for character in candidate)
        ):
            return fallback
        try:
            parsed = urlsplit(candidate)
        except ValueError:
            return fallback
        if parsed.scheme or parsed.netloc:
            return fallback
        decoded = unquote(candidate)
        if decoded == candidate:
            return candidate
        candidate = decoded
    return fallback


def _validate_password(password: str, confirmation: str | None = None) -> None:
    if len(password) < 10:
        raise DomainError("PASSWORD_TOO_SHORT", "Hasło musi mieć co najmniej 10 znaków.", 422)
    if len(password.encode("utf-8")) > 4096:
        raise DomainError("PASSWORD_TOO_LONG", "Hasło jest zbyt długie.", 422)
    if password.casefold() in _popular_passwords:
        raise DomainError("PASSWORD_TOO_COMMON", "To hasło jest zbyt popularne. Wybierz inne.", 422)
    if confirmation is not None and not hmac.compare_digest(password, confirmation):
        raise DomainError("PASSWORD_CONFIRMATION_MISMATCH", "Hasła nie są zgodne.", 422)


def _secure_cookie(response: Response, name: str, value: str, max_age: int | None = None) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        path="/api",
        secure=get_settings().ENVIRONMENT == "production",
        httponly=name == SESSION_COOKIE,
        samesite="lax",
    )


def _delete_cookie(response: Response, name: str) -> None:
    response.delete_cookie(
        name,
        path="/api",
        secure=get_settings().ENVIRONMENT == "production",
        httponly=name == SESSION_COOKIE,
        samesite="lax",
    )


def _origin_allowed(request: Request) -> bool:
    origin = request.headers.get("origin")
    settings = get_settings()
    if not origin:
        return False
    expected = urlsplit(settings.SITE_URL or "")
    actual = urlsplit(origin)
    if (
        expected.scheme
        and expected.netloc
        and (actual.scheme, actual.netloc) == (expected.scheme, expected.netloc)
    ):
        return True
    return (
        settings.ENVIRONMENT == "development"
        and actual.hostname in {"localhost", "127.0.0.1"}
        and actual.scheme in {"http", "https"}
    )


async def _require_csrf(request: Request, session: AsyncSession, csrf_header: str | None) -> None:
    cookie = request.cookies.get(CSRF_COOKIE)
    if (
        not _origin_allowed(request)
        or not cookie
        or not csrf_header
        or not hmac.compare_digest(cookie, csrf_header)
    ):
        raise DomainError(
            "CSRF_REJECTED",
            "Odśwież stronę i spróbuj ponownie.",
            403,
            headers=_PRIVATE_HEADERS,
        )
    customer_id = getattr(request.state, "customer_id", None)
    session_id = getattr(request.state, "account_session_id", None)
    if customer_id is not None and session_id is not None:
        row = await session.get(AccountSession, session_id)
        if row is None or not hmac.compare_digest(
            row.csrf_hash, hashlib.sha256(cookie.encode()).hexdigest()
        ):
            raise DomainError(
                "CSRF_REJECTED",
                "Odśwież stronę i spróbuj ponownie.",
                403,
                headers=_PRIVATE_HEADERS,
            )


def _client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    try:
        peer_ip = ipaddress.ip_address(peer)
    except ValueError:
        return "unknown"
    settings = get_settings()
    networks = []
    try:
        networks = [
            ipaddress.ip_network(part.strip(), strict=False)
            for part in settings.TRUSTED_PROXY_CIDRS.split(",")
            if part.strip()
        ]
    except ValueError:
        return str(peer_ip)
    if not any(peer_ip in network for network in networks):
        return str(peer_ip)
    try:
        chain = [
            ipaddress.ip_address(part.strip())
            for part in request.headers.get("x-forwarded-for", "").split(",")
        ]
    except ValueError:
        return str(peer_ip)
    for address in reversed(chain):
        if not any(address in network for network in networks):
            return str(address)
    return str(chain[0]) if chain else str(peer_ip)


def _key_hash(value: str) -> str:
    return digest_secret(value)


async def _record_failure(
    session: AsyncSession, scope: str, key: str, now: datetime, limit: int
) -> datetime | None:
    key_hash = _key_hash(key)
    stale_window = AuthAttempt.window_started_at < now - timedelta(minutes=15)
    statement = (
        insert(AuthAttempt)
        .values(
            scope=scope,
            key_hash=key_hash,
            failed_count=1,
            window_started_at=now,
        )
        .on_conflict_do_update(
            index_elements=[AuthAttempt.scope, AuthAttempt.key_hash],
            set_={
                "failed_count": case((stale_window, 1), else_=AuthAttempt.failed_count + 1),
                "window_started_at": case((stale_window, now), else_=AuthAttempt.window_started_at),
                "blocked_until": case(
                    (stale_window, None),
                    (AuthAttempt.failed_count + 1 >= limit, now + timedelta(minutes=15)),
                    else_=AuthAttempt.blocked_until,
                ),
            },
        )
        .returning(AuthAttempt.blocked_until)
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def _record_login_link_rate_event(
    session: AsyncSession,
    scope: str,
    identifier: str,
    now: datetime,
    limit: int,
) -> bool:
    """Atomically count one event in a configurable shared PostgreSQL window."""
    settings = get_settings()
    key_hash = _key_hash(identifier)
    stale_window = AuthAttempt.window_started_at < now - timedelta(
        seconds=settings.LOGIN_LINK_WINDOW_SECONDS
    )
    statement = (
        insert(AuthAttempt)
        .values(
            scope=scope,
            key_hash=key_hash,
            failed_count=1,
            window_started_at=now,
        )
        .on_conflict_do_update(
            index_elements=[AuthAttempt.scope, AuthAttempt.key_hash],
            set_={
                "failed_count": case((stale_window, 1), else_=AuthAttempt.failed_count + 1),
                "window_started_at": case((stale_window, now), else_=AuthAttempt.window_started_at),
                "blocked_until": case(
                    (stale_window, None),
                    (
                        AuthAttempt.failed_count + 1 >= limit,
                        now + timedelta(seconds=settings.LOGIN_LINK_COOLDOWN_SECONDS),
                    ),
                    else_=AuthAttempt.blocked_until,
                ),
            },
        )
        .returning(AuthAttempt.failed_count, AuthAttempt.blocked_until)
    )
    count, blocked_until = (await session.execute(statement)).one()
    return count >= limit or (blocked_until is not None and blocked_until > now)


async def _take_login_link_rate_limits(
    session: AsyncSession,
    email: str,
    client_ip: str,
    now: datetime,
    *,
    invalid_token: str | None = None,
) -> tuple[bool, int]:
    """Apply address and network quotas under deterministic transaction locks."""
    settings = get_settings()
    if invalid_token is not None:
        identifiers = [
            ("email", f"login-link-invalid-ip:{client_ip}", settings.LOGIN_LINK_INVALID_LIMIT),
            (
                "ip",
                f"login-link-invalid-token:{hashlib.sha256(invalid_token.encode()).hexdigest()}",
                settings.LOGIN_LINK_INVALID_LIMIT,
            ),
        ]
    else:
        identifiers = [
            ("email", f"login-link-email:{email}", settings.LOGIN_LINK_EMAIL_LIMIT),
            ("ip", f"login-link-ip:{client_ip}", settings.LOGIN_LINK_IP_LIMIT),
        ]
    hashed_locks = sorted(_key_hash(identifier) for _, identifier, _ in identifiers)
    for lock_key in hashed_locks:
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": lock_key}
        )
    blocked = False
    for scope, identifier, _ in identifiers:
        blocked = blocked or await _blocked(session, scope, identifier, now)
    if blocked:
        return True, settings.LOGIN_LINK_COOLDOWN_SECONDS
    for scope, identifier, limit in identifiers:
        blocked = (
            await _record_login_link_rate_event(session, scope, identifier, now, limit) or blocked
        )
    return blocked, settings.LOGIN_LINK_COOLDOWN_SECONDS


async def _blocked(session: AsyncSession, scope: str, key: str, now: datetime) -> bool:
    row = await session.scalar(
        select(AuthAttempt).where(
            AuthAttempt.scope == scope, AuthAttempt.key_hash == _key_hash(key)
        )
    )
    if row is None or row.blocked_until is None:
        return False
    if row.blocked_until <= now:
        row.failed_count = 0
        row.window_started_at = now
        row.blocked_until = None
        return False
    return True


def _token_pair() -> tuple[str, str, str]:
    selector = secrets.token_urlsafe(16)
    secret = secrets.token_urlsafe(32)
    return selector, secret, f"{selector}.{secret}"


def _new_login_link_token() -> str:
    """Generate a login-only bearer secret with 256 bits of entropy."""
    return secrets.token_urlsafe(32)


async def _pad_login_link_response(started_at: float) -> None:
    """Add non-blocking jitter so account lookup work is less observable by timing."""
    target_seconds = 0.14 + secrets.randbelow(120) / 1000
    remaining = target_seconds - (time.monotonic() - started_at)
    if remaining > 0:
        await asyncio.sleep(remaining)


def _encrypt_payload(payload: dict[str, str]) -> str:
    key = hashlib.sha256(
        get_settings().SECRET_KEY.get_secret_value().encode() + b"sensoria-auth-mail-v1"
    ).digest()
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(key).encrypt(
        nonce, json.dumps(payload, ensure_ascii=False).encode(), b"auth-email-v1"
    )
    import base64

    return base64.urlsafe_b64encode(nonce + ciphertext).decode()


async def _create_action_job(
    session: AsyncSession, customer: Customer, purpose: str, now: datetime
) -> None:
    await session.execute(
        update(AccountActionToken)
        .where(
            AccountActionToken.customer_id == customer.id,
            AccountActionToken.purpose == purpose,
            AccountActionToken.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )
    await session.execute(
        update(AuthEmailJob)
        .where(
            AuthEmailJob.customer_id == customer.id,
            AuthEmailJob.purpose == purpose,
            AuthEmailJob.status.in_(("pending", "queued")),
        )
        .values(status="cancelled", failure_code="superseded")
    )
    selector, secret, token = _token_pair()
    expires = now + (timedelta(hours=1) if purpose == "password_reset" else timedelta(hours=24))
    session.add(
        AccountActionToken(
            customer_id=customer.id,
            selector=selector,
            secret_hash=digest_secret(secret),
            purpose=purpose,
            expires_at=expires,
        )
    )
    # The worker derives the route and origin from trusted configuration.
    # Fragment tokens are not sent in HTTP requests/access logs or as a Referer.
    session.add(
        AuthEmailJob(
            customer_id=customer.id,
            purpose=purpose,
            payload_ciphertext=_encrypt_payload({"to": customer.email, "token": token}),
            idempotency_key=f"{purpose}:{selector}",
        )
    )


async def _new_session(
    session: AsyncSession, customer: Customer, remember: bool, now: datetime
) -> tuple[str, str, int]:
    raw = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    idle_seconds = 14 * 86400 if remember else 12 * 3600
    absolute_seconds = 30 * 86400 if remember else 7 * 86400
    row = AccountSession(
        customer_id=customer.id,
        secret_hash=digest_secret(raw),
        csrf_hash=hashlib.sha256(csrf.encode()).hexdigest(),
        reauthenticated_at=now,
        last_seen_at=now,
        idle_expires_at=now + timedelta(seconds=idle_seconds),
        absolute_expires_at=now + timedelta(seconds=absolute_seconds),
        remember_me=remember,
    )
    session.add(row)
    return raw, csrf, absolute_seconds


def _audit(
    actor_id: Any, action: str, entity_id: Any, payload: dict[str, Any] | None = None
) -> AuditLog:
    return AuditLog(
        actor_type=ActorType.CUSTOMER if actor_id else ActorType.SYSTEM,
        actor_id=actor_id,
        entity_type="customer_account" if actor_id else "auth_attempt",
        entity_id=entity_id or uuid4(),
        action=action,
        payload=payload or {},
    )


async def _get_customer(session: AsyncSession, customer_id: Any) -> Customer | None:
    return await session.get(Customer, customer_id)


@router.get("/csrf")
async def csrf_token(
    request: Request, response: Response, session: SessionDependency
) -> dict[str, str]:
    """Issue a double-submit CSRF token; rotate/bind it to an authenticated session."""
    raw = request.cookies.get(CSRF_COOKIE)
    session_id = getattr(request.state, "account_session_id", None)
    if not raw or len(raw) < 32:
        raw = secrets.token_urlsafe(32)
    if session_id:
        row = await session.get(AccountSession, session_id)
        if row is not None and not hmac.compare_digest(
            row.csrf_hash, hashlib.sha256(raw.encode()).hexdigest()
        ):
            row.csrf_hash = hashlib.sha256(raw.encode()).hexdigest()
            await session.commit()
    _secure_cookie(response, CSRF_COOKIE, raw, 86400)
    response.headers.update({"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
    return {"csrf_token": raw}


@auth_router.post("/login-link")
async def request_login_link(
    payload: LoginLinkInput,
    request: Request,
    response: Response,
    session: SessionDependency,
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    """Create an encrypted email intent without disclosing whether the account exists."""
    await _require_csrf(request, session, x_csrf_token)
    started_at = time.monotonic()
    email = normalize_email(payload.email)
    now = utc_now()
    client_ip = _client_ip(request)
    rate_limited, retry_after = await _take_login_link_rate_limits(session, email, client_ip, now)
    session.add(
        _audit(
            None,
            "login_link_rate_limited" if rate_limited else "login_link_requested",
            None,
            {"email_hash": _key_hash(email), "ip_hash": _key_hash(client_ip)},
        )
    )
    if rate_limited:
        await session.commit()
        await _pad_login_link_response(started_at)
        raise DomainError(
            "LOGIN_LINK_RATE_LIMITED",
            _LOGIN_LINK_MESSAGE,
            429,
            headers={**_PRIVATE_HEADERS, "Retry-After": str(retry_after)},
        )

    address_lock = _key_hash("login-link-request:" + email)
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": address_lock}
    )
    customer = await session.scalar(
        select(Customer)
        .where(Customer.email == email, Customer.deleted_at.is_(None))
        .with_for_update()
    )
    if customer is not None:
        await session.execute(
            update(LoginLink)
            .where(
                LoginLink.customer_id == customer.id,
                LoginLink.used_at.is_(None),
                LoginLink.invalidated_at.is_(None),
            )
            .values(invalidated_at=now)
        )
        await session.execute(
            update(AuthEmailJob)
            .where(
                AuthEmailJob.customer_id == customer.id,
                AuthEmailJob.purpose == "login_link",
                AuthEmailJob.status.in_(("pending", "queued")),
            )
            .values(
                status="cancelled",
                failure_code="superseded",
                payload_ciphertext="",
            )
        )
        token = _new_login_link_token()
        expires_at = now + timedelta(minutes=15)
        job_id = uuid4()
        link_id = uuid4()
        login_link = LoginLink(
            id=link_id,
            customer_id=customer.id,
            token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            expires_at=expires_at,
            requested_ip=_key_hash("login-link-ip:" + client_ip),
            return_to=safe_login_return_path(payload.return_to),
            email_job_id=job_id,
        )
        mail_job = AuthEmailJob(
            id=job_id,
            customer_id=customer.id,
            purpose="login_link",
            payload_ciphertext=_encrypt_payload({"to": customer.email, "token": token}),
            idempotency_key=f"login_link:{link_id}",
        )
        session.add_all([login_link, mail_job])
    response.headers.update(_PRIVATE_HEADERS)
    await session.commit()
    await _pad_login_link_response(started_at)
    return {"message": _LOGIN_LINK_MESSAGE}


@auth_router.get("/login-link/{token}")
async def inspect_login_link(
    token: str,
    response: Response,
    session: SessionDependency,
) -> dict[str, bool]:
    """GET is a read-only scanner-safe validity check."""
    response.headers.update(_PRIVATE_HEADERS)
    token_hash = hashlib.sha256(token[:512].encode("utf-8")).hexdigest()
    row = await session.scalar(select(LoginLink).where(LoginLink.token_hash == token_hash))
    valid = bool(
        row is not None
        and hmac.compare_digest(row.token_hash, token_hash)
        and row.used_at is None
        and row.invalidated_at is None
        and row.expires_at > utc_now()
    )
    return {"valid": valid}


@auth_router.head("/login-link/{token}", include_in_schema=False)
async def inspect_login_link_head() -> Response:
    """HEAD is deliberately non-consuming and does not expose a token status."""
    return Response(status_code=204, headers=_PRIVATE_HEADERS)


@auth_router.post("/login-link/{token}")
async def consume_login_link(
    token: str,
    request: Request,
    response: Response,
    session: SessionDependency,
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Atomically consume a link and rotate/create the existing account session."""
    await _require_csrf(request, session, x_csrf_token)
    now = utc_now()
    client_ip = _client_ip(request)
    token_hash = hashlib.sha256(token[:512].encode("utf-8")).hexdigest()
    candidate = await session.scalar(select(LoginLink).where(LoginLink.token_hash == token_hash))
    link: LoginLink | None = None
    customer: Customer | None = None
    if candidate is not None:
        customer = await session.scalar(
            select(Customer).where(Customer.id == candidate.customer_id).with_for_update()
        )
        if customer is not None:
            link = await session.scalar(
                select(LoginLink)
                .where(LoginLink.id == candidate.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
    if (
        link is None
        or customer is None
        or not hmac.compare_digest(link.token_hash, token_hash)
        or link.used_at is not None
        or link.invalidated_at is not None
        or link.expires_at <= now
    ):
        limited, retry_after = await _take_login_link_rate_limits(
            session, "invalid", client_ip, now, invalid_token=token
        )
        session.add(
            _audit(
                None,
                "login_link_rejected",
                None,
                {"reason": "invalid_or_expired", "ip_hash": _key_hash(client_ip)},
            )
        )
        await session.commit()
        if limited:
            raise DomainError(
                "LOGIN_LINK_RATE_LIMITED",
                _LOGIN_LINK_INVALID_MESSAGE,
                429,
                headers={**_PRIVATE_HEADERS, "Retry-After": str(retry_after)},
            )
        raise DomainError(
            "LOGIN_LINK_INVALID",
            _LOGIN_LINK_INVALID_MESSAGE,
            400,
            headers=_PRIVATE_HEADERS,
        )

    if await _blocked(session, "email", customer.email, now) or await _blocked(
        session, "ip", client_ip, now
    ):
        session.add(
            _audit(customer.id, "login_link_rejected", link.id, {"reason": "security_lock"})
        )
        await session.commit()
        raise DomainError(
            "LOGIN_LINK_TEMPORARILY_BLOCKED",
            "Nie można teraz zalogować. Spróbuj ponownie później.",
            429,
            headers={**_PRIVATE_HEADERS, "Retry-After": "900"},
        )

    current_cookie = request.cookies.get(SESSION_COOKIE)
    current_session: AccountSession | None = None
    if current_cookie:
        current_session = await session.scalar(
            select(AccountSession)
            .where(
                AccountSession.secret_hash == digest_secret(current_cookie),
                AccountSession.revoked_at.is_(None),
                AccountSession.idle_expires_at > now,
                AccountSession.absolute_expires_at > now,
            )
            .with_for_update()
        )
    if current_session is not None and current_session.customer_id != customer.id:
        session.add(
            _audit(customer.id, "login_link_rejected", link.id, {"reason": "other_session"})
        )
        await session.commit()
        raise DomainError(
            "LOGIN_LINK_DIFFERENT_ACCOUNT",
            "W tej przeglądarce jest zalogowane inne konto. "
            "Wyloguj się, a następnie otwórz link ponownie.",
            409,
            headers=_PRIVATE_HEADERS,
        )

    if current_session is not None:
        current_session.revoked_at = now
    link.used_at = now
    customer.last_login_at = now
    # Possession of this emailed credential demonstrates control of this mailbox.
    if customer.email_verified_at is None:
        customer.email_verified_at = now
    raw, csrf_value, max_age = await _new_session(session, customer, False, now)
    purchase_linking = await reconcile_guest_purchases(
        session, customer.id, source="login_link", at=now
    )
    await session.execute(
        delete(AuthAttempt).where(
            ((AuthAttempt.scope == "email") & (AuthAttempt.key_hash == _key_hash(customer.email)))
            | ((AuthAttempt.scope == "ip") & (AuthAttempt.key_hash == _key_hash(client_ip)))
        )
    )
    session.add(_audit(customer.id, "login_link_used", link.id))
    session.add(_audit(customer.id, "session_created", customer.id, {"method": "login_link"}))
    await session.commit()
    _secure_cookie(response, SESSION_COOKIE, raw, max_age)
    _secure_cookie(response, CSRF_COOKIE, csrf_value, 86400)
    response.headers.update(_PRIVATE_HEADERS)
    return {
        "redirect_to": safe_login_return_path(link.return_to),
        "purchase_linking": purchase_linking.as_dict(),
    }


@router.post("/register", status_code=201)
async def register(
    payload: RegisterInput,
    request: Request,
    response: Response,
    session: SessionDependency,
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    await _require_csrf(request, session, x_csrf_token)
    email = normalize_email(payload.email)
    if await session.scalar(
        select(DeletedEmailSuppression.id).where(
            DeletedEmailSuppression.email_digest == deleted_email_digest(email)
        )
    ):
        raise DomainError(
            "EMAIL_ALREADY_REGISTERED",
            "Nie można utworzyć konta z tym adresem e-mail.",
            409,
        )
    _validate_password(payload.password)
    first_name = payload.first_name.strip()
    last_name = payload.last_name.strip()
    if not first_name or not last_name:
        raise DomainError("NAME_REQUIRED", "Podaj imię i nazwisko.", 422)
    now = utc_now()
    password_hash = await run_in_threadpool(hasher.hash, payload.password)
    customer = Customer(
        email=email,
        password_hash=password_hash,
        first_name=first_name,
        last_name=last_name,
        phone=payload.phone.strip() if payload.phone else None,
    )
    session.add(customer)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise DomainError(
            "EMAIL_ALREADY_REGISTERED", "Konto z tym adresem e-mail już istnieje.", 409
        ) from None
    await _create_action_job(session, customer, "email_verification", now)
    raw, csrf, max_age = await _new_session(session, customer, False, now)
    purchase_linking = None
    if customer.email_verified_at is not None:
        purchase_linking = await reconcile_guest_purchases(
            session, customer.id, source="registration", at=now
        )
    session.add(_audit(customer.id, "registered", customer.id))
    await session.commit()
    _secure_cookie(response, SESSION_COOKIE, raw, max_age)
    _secure_cookie(response, CSRF_COOKIE, csrf, 86400)
    response.headers.update(
        {"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"}
    )
    return {
        "customer": {
            "id": str(customer.id),
            "email": email,
            "first_name": customer.first_name,
            "last_name": customer.last_name,
            "email_verified": False,
        },
        "verification_message": (
            "Potwierdź adres e-mail z wiadomości. Z konta możesz korzystać już teraz."
        ),
        "purchase_linking": purchase_linking.as_dict() if purchase_linking else None,
    }


@router.post("/login")
async def login(
    payload: LoginInput,
    request: Request,
    response: Response,
    session: SessionDependency,
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    await _require_csrf(request, session, x_csrf_token)
    email = normalize_email(payload.email)
    now = utc_now()
    ip = _client_ip(request)
    blocked = await _blocked(session, "email", email, now) or await _blocked(session, "ip", ip, now)
    customer = await session.scalar(
        select(Customer).where(Customer.email == email, Customer.deleted_at.is_(None))
    )
    # Hash verification always runs, including unknown and currently blocked identities.
    encoded = customer.password_hash if customer is not None else _dummy_password_hash
    try:
        password_ok: bool = await run_in_threadpool(hasher.verify, encoded, payload.password)
    except (VerifyMismatchError, InvalidHashError):
        password_ok = False
    if blocked or customer is None or not password_ok:
        if not blocked:
            email_blocked_until = await _record_failure(session, "email", email, now, 10)
            ip_blocked_until = await _record_failure(session, "ip", ip, now, 50)
            blocked = any(
                until is not None and until > now
                for until in (email_blocked_until, ip_blocked_until)
            )
        session.add(
            _audit(
                None,
                "login_failed",
                uuid4(),
                {
                    "email_hash": _key_hash(email),
                    "ip_hash": _key_hash(ip),
                    "blocked": blocked,
                },
            )
        )
        await session.commit()
        response.headers.update({"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
        if blocked:
            response.headers["Retry-After"] = "900"
            raise DomainError(
                "LOGIN_TEMPORARILY_BLOCKED",
                _GENERIC_LOGIN_ERROR,
                429,
                {**_PRIVATE_HEADERS, "Retry-After": "900"},
            )
        raise DomainError("INVALID_CREDENTIALS", _GENERIC_LOGIN_ERROR, 401, _PRIVATE_HEADERS)
    try:
        if hasher.check_needs_rehash(customer.password_hash):
            customer.password_hash = await run_in_threadpool(hasher.hash, payload.password)
    except InvalidHashError:
        raise DomainError(
            "INVALID_CREDENTIALS", _GENERIC_LOGIN_ERROR, 401, _PRIVATE_HEADERS
        ) from None
    customer.last_login_at = now
    existing_session_token = request.cookies.get(SESSION_COOKIE)
    if existing_session_token:
        await session.execute(
            update(AccountSession)
            .where(
                AccountSession.customer_id == customer.id,
                AccountSession.secret_hash == digest_secret(existing_session_token),
                AccountSession.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
    raw, csrf, max_age = await _new_session(session, customer, payload.remember_me, now)
    purchase_linking = None
    if customer.email_verified_at is not None:
        purchase_linking = await reconcile_guest_purchases(
            session, customer.id, source="password_login", at=now
        )
    await session.execute(
        delete(AuthAttempt).where(
            ((AuthAttempt.scope == "email") & (AuthAttempt.key_hash == _key_hash(email)))
            | ((AuthAttempt.scope == "ip") & (AuthAttempt.key_hash == _key_hash(ip)))
        )
    )
    session.add(_audit(customer.id, "login_succeeded", customer.id))
    await session.commit()
    _secure_cookie(response, SESSION_COOKIE, raw, max_age)
    _secure_cookie(response, CSRF_COOKIE, csrf, 86400)
    response.headers.update(
        {"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"}
    )
    return {
        "customer": {
            "id": str(customer.id),
            "email": email,
            "first_name": customer.first_name,
            "last_name": customer.last_name,
            "email_verified": customer.email_verified_at is not None,
        },
        "purchase_linking": purchase_linking.as_dict() if purchase_linking else None,
        "purchase_history_notice": customer.email_verified_at is None,
    }


@router.get("/session")
async def current_session(
    response: Response, session: SessionDependency, customer_id: CustomerDependency
) -> dict[str, Any]:
    response.headers.update(
        {
            "Cache-Control": "private, no-store",
            "Referrer-Policy": "no-referrer",
            "X-Robots-Tag": "noindex",
        }
    )
    customer = await _get_customer(session, customer_id)
    if customer is None:
        raise DomainError(
            "AUTHENTICATION_REQUIRED", "Zaloguj się, aby zobaczyć dane swojego konta.", 401
        )
    return {
        "customer": {
            "id": str(customer.id),
            "email": customer.email,
            "first_name": customer.first_name,
            "last_name": customer.last_name,
            "phone": customer.phone,
            "email_verified": customer.email_verified_at is not None,
        },
        "purchase_history_notice": customer.email_verified_at is None,
    }


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    session: SessionDependency,
    customer_id: CustomerDependency,
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> Response:
    await _require_csrf(request, session, x_csrf_token)
    row = await session.get(AccountSession, request.state.account_session_id)
    if row is not None and row.revoked_at is None:
        row.revoked_at = utc_now()
    session.add(_audit(customer_id, "logout", customer_id))
    await session.commit()
    _delete_cookie(response, SESSION_COOKIE)
    _delete_cookie(response, CSRF_COOKIE)
    response.headers.update({"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
    response.status_code = 204
    return response


@router.post("/password-reset/request")
async def request_password_reset(
    payload: EmailInput,
    request: Request,
    response: Response,
    session: SessionDependency,
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    await _require_csrf(request, session, x_csrf_token)
    email = normalize_email(payload.email)
    now = utc_now()
    # Keyed limiter; unknown addresses never create customer records.
    key_hash = _key_hash("reset:" + email)
    await session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": key_hash})
    recent = await session.scalar(
        select(func.count())
        .select_from(AuthEmailJob)
        .join(Customer)
        .where(
            AuthEmailJob.customer_id == Customer.id,
            AuthEmailJob.purpose == "password_reset",
            AuthEmailJob.created_at >= now - timedelta(hours=1),
            Customer.email == email,
        )
    )
    customer = await session.scalar(select(Customer).where(Customer.email == email))
    if customer is not None and (recent or 0) < 3:
        await _create_action_job(session, customer, "password_reset", now)
        session.add(_audit(customer.id, "password_reset_requested", customer.id))
    else:
        session.add(
            _audit(
                None,
                "password_reset_requested",
                uuid4(),
                {"email_hash": _key_hash(email), "queued": False},
            )
        )
    response.headers.update({"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
    await session.commit()
    return {"message": _RESET_MESSAGE}


async def _consume_token(
    session: AsyncSession, raw_token: str, purpose: str, now: datetime
) -> AccountActionToken:
    if "." not in raw_token:
        raise DomainError(
            "ACTION_TOKEN_INVALID",
            "Link jest nieprawidłowy lub wygasł. Poproś o nową wiadomość.",
            400,
        )
    selector, secret = raw_token.split(".", 1)
    row = await session.scalar(
        select(AccountActionToken)
        .where(AccountActionToken.selector == selector, AccountActionToken.purpose == purpose)
        .with_for_update()
    )
    provided = digest_secret(secret)
    expected = row.secret_hash if row is not None else "0" * 64
    valid = hmac.compare_digest(provided, expected)
    if row is None or not valid or row.consumed_at is not None or row.expires_at <= now:
        raise DomainError(
            "ACTION_TOKEN_INVALID",
            "Link jest nieprawidłowy lub wygasł. Poproś o nową wiadomość.",
            400,
        )
    return row


@router.post("/password-reset/confirm")
async def reset_password(
    payload: PasswordInput,
    request: Request,
    response: Response,
    session: SessionDependency,
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    await _require_csrf(request, session, x_csrf_token)
    _validate_password(payload.password, payload.password_confirmation)
    now = utc_now()
    token = await _consume_token(session, payload.token, "password_reset", now)
    customer = await session.scalar(
        select(Customer).where(Customer.id == token.customer_id).with_for_update()
    )
    if customer is None:
        raise DomainError(
            "ACTION_TOKEN_INVALID",
            "Link jest nieprawidłowy lub wygasł. Poproś o nową wiadomość.",
            400,
        )
    customer.password_hash = await run_in_threadpool(hasher.hash, payload.password)
    token.consumed_at = now
    await session.execute(
        update(AccountActionToken)
        .where(
            AccountActionToken.customer_id == customer.id, AccountActionToken.consumed_at.is_(None)
        )
        .values(consumed_at=now)
    )
    await session.execute(
        update(AccountSession)
        .where(AccountSession.customer_id == customer.id, AccountSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    session.add(_audit(customer.id, "password_reset_completed", customer.id))
    await session.commit()
    response.headers.update({"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
    return {"message": "Hasło zostało zmienione. Zaloguj się ponownie."}


@router.post("/password/change")
async def change_password(
    payload: ChangePasswordInput,
    request: Request,
    response: Response,
    session: SessionDependency,
    customer_id: CustomerDependency,
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    await _require_csrf(request, session, x_csrf_token)
    _validate_password(payload.password, payload.password_confirmation)
    customer = await session.scalar(
        select(Customer).where(Customer.id == customer_id).with_for_update()
    )
    if customer is None:
        raise DomainError("AUTHENTICATION_REQUIRED", "Zaloguj się ponownie.", 401)
    try:
        valid: bool = await run_in_threadpool(
            hasher.verify, customer.password_hash, payload.current_password
        )
    except (VerifyMismatchError, InvalidHashError):
        valid = False
    if not valid:
        raise DomainError("CURRENT_PASSWORD_INVALID", "Bieżące hasło jest nieprawidłowe.", 400)
    now = utc_now()
    customer.password_hash = await run_in_threadpool(hasher.hash, payload.password)
    old_id = request.state.account_session_id
    await session.execute(
        update(AccountSession)
        .where(
            AccountSession.customer_id == customer.id,
            AccountSession.id != old_id,
            AccountSession.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    old = await session.get(AccountSession, old_id)
    if old is not None:
        old.revoked_at = now
    raw, csrf, max_age = await _new_session(
        session, customer, bool(old.remember_me) if old else False, now
    )
    await session.execute(
        update(AccountActionToken)
        .where(
            AccountActionToken.customer_id == customer.id, AccountActionToken.consumed_at.is_(None)
        )
        .values(consumed_at=now)
    )
    session.add(_audit(customer.id, "password_changed", customer.id))
    await session.commit()
    _secure_cookie(response, SESSION_COOKIE, raw, max_age)
    _secure_cookie(response, CSRF_COOKIE, csrf, 86400)
    response.headers.update(
        {"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"}
    )
    return {"message": "Hasło zostało zmienione."}


@router.post("/email/verify")
async def verify_email(
    payload: dict[str, str],
    request: Request,
    response: Response,
    session: SessionDependency,
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    await _require_csrf(request, session, x_csrf_token)
    token_text = payload.get("token", "")
    now = utc_now()
    token = await _consume_token(session, token_text, "email_verification", now)
    customer = await session.scalar(
        select(Customer).where(Customer.id == token.customer_id).with_for_update()
    )
    if customer is not None:
        customer.email_verified_at = now
        token.consumed_at = now
        await session.execute(
            update(AccountActionToken)
            .where(
                AccountActionToken.customer_id == customer.id,
                AccountActionToken.purpose == "email_verification",
                AccountActionToken.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )
        session.add(_audit(customer.id, "email_verified", customer.id))
        purchase_linking = await reconcile_guest_purchases(
            session, customer.id, source="email_verification", at=now
        )
    else:
        purchase_linking = None
    await session.commit()
    response.headers.update({"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
    return {
        "message": "Adres e-mail został potwierdzony.",
        "purchase_linking": purchase_linking.as_dict() if purchase_linking else None,
    }


@router.post("/email/verification-resend")
async def resend_verification(
    request: Request,
    response: Response,
    session: SessionDependency,
    customer_id: CustomerDependency,
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    await _require_csrf(request, session, x_csrf_token)
    now = utc_now()
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": str(customer_id)}
    )
    customer = await session.scalar(
        select(Customer).where(Customer.id == customer_id).with_for_update()
    )
    if customer is not None and customer.email_verified_at is None:
        recent = await session.scalar(
            select(func.count())
            .select_from(AuthEmailJob)
            .where(
                AuthEmailJob.customer_id == customer.id,
                AuthEmailJob.purpose == "email_verification",
                AuthEmailJob.created_at >= now - timedelta(hours=1),
            )
        )
        if (recent or 0) < 3:
            await _create_action_job(session, customer, "email_verification", now)
    await session.commit()
    response.headers.update({"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
    return {"message": "Jeśli potwierdzenie jest potrzebne, zlecono wysłanie wiadomości."}
