"""Administrator accounts and revocable sessions."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from sensoria.database import Base, UUIDMixin

ROLES = ("owner", "staff")


class AdminUser(UUIDMixin, Base):
    """Panel operator. Roles: owner (everything) and staff (day-to-day operations)."""

    __tablename__ = "admin_users"
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'staff')", name="valid_role"),
        CheckConstraint("email = lower(btrim(email))", name="normalized_email"),
        CheckConstraint("failed_attempts >= 0", name="nonnegative_failed_attempts"),
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="true")
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AdminSession(UUIDMixin, Base):
    """Server-side session; only digests of the cookie and CSRF secrets are stored."""

    __tablename__ = "admin_sessions"
    __table_args__ = (Index("ix_admin_sessions_user", "admin_id"),)

    admin_id: Mapped[UUID] = mapped_column(
        ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False
    )
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip_hash: Mapped[str | None] = mapped_column(String(64))
