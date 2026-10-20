"""Administrator authentication: password login, lockout, sessions, CSRF and role checks."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, Request, Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.config import get_settings
from sensoria.database import get_session
from sensoria.modules.accounts.auth import digest_secret
from sensoria.shared.audit_log import ActorType, AuditLog
from sensoria.shared.errors import DomainError

from .models import AdminSession, AdminUser

SESSION_COOKIE = "sensoria_admin_session"
IDLE_TTL = timedelta(hours=2)
ABSOLUTE_TTL = timedelta(hours=12)
MAX_FAILED = 5
LOCK_FOR = timedelta(minutes=15)
MIN_PASSWORD_LENGTH = 12
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
hasher = PasswordHasher(
    type=Type.ID, time_cost=3, memory_cost=65_536, parallelism=2, hash_len=32, salt_len=16
)
_DUMMY_HASH = hasher.hash("sensoria-dummy-admin-password")
GENERIC_LOGIN_ERROR = "Nieprawidłowy adres e-mail lub hasło."
NO_STORE = {"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"}


@dataclass(frozen=True, slots=True)
class AdminPrincipal:
    """Trusted identity resolved from a revocable server-side session."""

    id: UUID
    role: str = "owner"
    email: str = ""
    display_name: str = ""
    session_id: UUID | None = None


def validate_new_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH or password.lower() == password.upper():
        raise DomainError(
            "ADMIN_PASSWORD_WEAK",
            f"Hasło musi mieć co najmniej {MIN_PASSWORD_LENGTH} znaków i zawierać litery.",
            422,
        )


def _csrf_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _origin_ok(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return False
    settings = get_settings()
    actual = urlsplit(origin)
    expected = urlsplit(settings.SITE_URL or "")
    if expected.netloc and (actual.scheme, actual.netloc) == (expected.scheme, expected.netloc):
        return True
    return settings.ENVIRONMENT == "development" and actual.hostname in {"localhost", "127.0.0.1"}


def _unauthenticated() -> DomainError:
    return DomainError(
        "ADMIN_AUTHENTICATION_REQUIRED", "Zaloguj się do panelu.", 401, headers=NO_STORE
    )


async def login_admin(
    session: AsyncSession, request: Request, response: Response, email: str, password: str
) -> tuple[AdminUser, str]:
    """Verify credentials with uniform timing, lock out brute force, open a session."""
    from sensoria.modules.accounts.privacy import hashed_client_ip

    now = datetime.now(UTC)
    user = await session.scalar(
        select(AdminUser).where(AdminUser.email == email.strip().lower()).with_for_update()
    )
    encoded = user.password_hash if user is not None else _DUMMY_HASH
    ok: bool
    try:
        ok = bool(await run_in_threadpool(hasher.verify, encoded, password))
    except (VerifyMismatchError, InvalidHashError):
        ok = False
    locked = user is not None and user.locked_until is not None and user.locked_until > now
    if user is None or not user.is_active or locked or not ok:
        if user is not None and not locked:
            user.failed_attempts += 1
            if user.failed_attempts >= MAX_FAILED:
                user.locked_until = now + LOCK_FOR
                user.failed_attempts = 0
        session.add(
            AuditLog(
                actor_type=ActorType.SYSTEM,
                actor_id=None,
                entity_type="admin_login",
                entity_id=uuid4(),
                action="admin.login_failed",
                payload={"known_user": user is not None, "locked": locked},
            )
        )
        await session.commit()
        if locked:
            raise DomainError(
                "ADMIN_LOGIN_LOCKED",
                GENERIC_LOGIN_ERROR,
                429,
                {**NO_STORE, "Retry-After": "900"},
            )
        raise DomainError("ADMIN_INVALID_CREDENTIALS", GENERIC_LOGIN_ERROR, 401, NO_STORE)
    if hasher.check_needs_rehash(user.password_hash):
        user.password_hash = await run_in_threadpool(hasher.hash, password)
    user.failed_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    raw, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    session.add(
        AdminSession(
            admin_id=user.id,
            secret_hash=digest_secret("admin:" + raw),
            csrf_hash=_csrf_digest(csrf),
            idle_expires_at=now + IDLE_TTL,
            absolute_expires_at=now + ABSOLUTE_TTL,
            ip_hash=hashed_client_ip(request),
        )
    )
    session.add(
        AuditLog(
            actor_type=ActorType.ADMINISTRATOR,
            actor_id=user.id,
            entity_type="admin_user",
            entity_id=user.id,
            action="admin.login",
            payload={},
        )
    )
    await session.commit()
    response.set_cookie(
        SESSION_COOKIE,
        raw,
        max_age=int(ABSOLUTE_TTL.total_seconds()),
        path="/api/admin",
        secure=get_settings().ENVIRONMENT == "production",
        httponly=True,
        samesite="strict",
    )
    return user, csrf


async def require_admin_principal(
    request: Request, session: Annotated[AsyncSession, Depends(get_session)]
) -> AdminPrincipal:
    """Resolve the session; unsafe methods also need Origin and the CSRF header."""
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        raise _unauthenticated()
    now = datetime.now(UTC)
    row = await session.scalar(
        select(AdminSession)
        .join(AdminUser, AdminUser.id == AdminSession.admin_id)
        .where(
            AdminSession.secret_hash == digest_secret("admin:" + raw),
            AdminSession.revoked_at.is_(None),
            AdminSession.idle_expires_at > now,
            AdminSession.absolute_expires_at > now,
            AdminUser.is_active.is_(True),
        )
    )
    if row is None:
        raise _unauthenticated()
    if request.method not in SAFE_METHODS:
        header = request.headers.get("x-csrf-token", "")
        if not _origin_ok(request) or not hmac.compare_digest(_csrf_digest(header), row.csrf_hash):
            raise DomainError(
                "ADMIN_CSRF_REJECTED", "Odśwież panel i spróbuj ponownie.", 403, NO_STORE
            )
    user = await session.get(AdminUser, row.admin_id)
    assert user is not None
    row.idle_expires_at = min(now + IDLE_TTL, row.absolute_expires_at)
    await session.commit()
    request.state.admin_id = user.id
    return AdminPrincipal(
        id=user.id,
        role=user.role,
        email=user.email,
        display_name=user.display_name,
        session_id=row.id,
    )


def require_role(*roles: str) -> Callable[[AdminPrincipal], Awaitable[AdminPrincipal]]:
    """Dependency factory restricting an endpoint to the listed roles."""

    async def dependency(
        principal: Annotated[AdminPrincipal, Depends(require_admin_principal)],
    ) -> AdminPrincipal:
        if principal.role not in roles:
            raise DomainError(
                "ADMIN_FORBIDDEN", "Brak uprawnień do tej operacji.", 403, headers=NO_STORE
            )
        return principal

    return dependency


async def logout_admin(
    session: AsyncSession, principal: AdminPrincipal, response: Response
) -> None:
    await session.execute(
        update(AdminSession)
        .where(AdminSession.id == principal.session_id)
        .values(revoked_at=datetime.now(UTC))
    )
    await session.commit()
    response.delete_cookie(SESSION_COOKIE, path="/api/admin")
