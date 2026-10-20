"""Information pages; content is structured data and never raw HTML."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from sensoria.database import Base, UUIDMixin


class ContentPage(UUIDMixin, Base):
    __tablename__ = "content_pages"
    __table_args__ = (
        CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="valid_slug"),
        CheckConstraint("status IN ('draft', 'published')", name="valid_status"),
        CheckConstraint("length(btrim(title)) > 0", name="nonempty_title"),
    )

    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(300))
    blocks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="draft")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="SET NULL")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FaqEntry(UUIDMixin, Base):
    """Help-center question; answers are plain text paragraphs separated by blank lines."""

    __tablename__ = "faq_entries"
    __table_args__ = (
        CheckConstraint("length(btrim(question)) > 0", name="nonempty_question"),
        CheckConstraint("length(btrim(answer)) > 0", name="nonempty_answer"),
    )

    category: Mapped[str] = mapped_column(String(60), nullable=False)
    question: Mapped[str] = mapped_column(String(300), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    published: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CookieConsent(UUIDMixin, Base):
    """Append-only register of cookie choices; the latest row per subject is current."""

    __tablename__ = "cookie_consents"
    __table_args__ = (Index("ix_cookie_consents_subject_created", "subject_id", "created_at"),)

    subject_id: Mapped[UUID] = mapped_column(nullable=False)
    policy_version: Mapped[str] = mapped_column(String(20), nullable=False)
    analytics: Mapped[bool] = mapped_column(nullable=False)
    marketing: Mapped[bool] = mapped_column(nullable=False)
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
