"""PostgreSQL-backed fixed-window rate limiting shared by all API workers."""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta

from fastapi import Request
from sqlalchemy import DateTime, Index, Integer, String, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from sensoria.config import get_settings
from sensoria.database import Base, UUIDMixin
from sensoria.shared.errors import DomainError


class RateLimitWindow(UUIDMixin, Base):
    """One counter per (scope, hashed subject, window start); old windows are pruned."""

    __tablename__ = "rate_limit_windows"
    __table_args__ = (
        Index(
            "uq_rate_limit_windows_subject",
            "scope",
            "subject_hash",
            "window_started_at",
            unique=True,
        ),
    )

    scope: Mapped[str] = mapped_column(String(40), nullable=False)
    subject_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    hits: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


def subject_digest(scope: str, subject: str) -> str:
    key = get_settings().SECRET_KEY.get_secret_value().encode()
    return hmac.new(key, f"rate:{scope}:{subject}".encode(), hashlib.sha256).hexdigest()


def client_subject(request: Request) -> str:
    from sensoria.modules.accounts.privacy import hashed_client_ip

    return hashed_client_ip(request) or "unknown"


async def enforce_rate_limit(
    session: AsyncSession,
    request: Request,
    *,
    scope: str,
    limit: int,
    window_seconds: int,
) -> None:
    """Count this request and raise 429 once the window's budget is spent."""
    now = datetime.now(UTC)
    epoch = int(now.timestamp())
    start = datetime.fromtimestamp(epoch - epoch % window_seconds, UTC)
    hits = await session.scalar(
        pg_insert(RateLimitWindow)
        .values(
            scope=scope,
            subject_hash=subject_digest(scope, client_subject(request)),
            window_started_at=start,
            hits=1,
        )
        .on_conflict_do_update(
            index_elements=["scope", "subject_hash", "window_started_at"],
            set_={"hits": RateLimitWindow.hits + 1},
        )
        .returning(RateLimitWindow.hits)
    )
    # Opportunistic pruning keeps the table tiny without a separate job.
    if int(now.timestamp()) % 50 == 0:
        await session.execute(
            delete(RateLimitWindow).where(
                RateLimitWindow.window_started_at < now - timedelta(hours=2)
            )
        )
    await session.commit()
    if (hits or 0) > limit:
        retry_after = max(1, int(window_seconds - (now - start).total_seconds()))
        raise DomainError(
            "RATE_LIMITED",
            "Zbyt wiele prób. Spróbuj ponownie za chwilę.",
            429,
            {"Retry-After": str(retry_after), "Cache-Control": "no-store"},
        )
