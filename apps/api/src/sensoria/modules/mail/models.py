"""Durable outbound message log; every send attempt is traceable by outbox id."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from sensoria.database import Base, TimestampMixin, UUIDMixin

OUTBOX_STATUSES = ("pending", "sending", "sent", "retry", "failed", "cancelled")


class MailOutbox(UUIDMixin, TimestampMixin, Base):
    """One message; the unique idempotency key prevents duplicate enqueueing."""

    __tablename__ = "mail_outbox"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'sending', 'sent', 'retry', 'failed', 'cancelled')",
            name="valid_status",
        ),
        CheckConstraint("attempts >= 0", name="nonnegative_attempts"),
        Index("ix_mail_outbox_dispatch", "status", "next_attempt_at"),
        Index("ix_mail_outbox_recipient", "recipient"),
    )

    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    template_key: Mapped[str] = mapped_column(String(60), nullable=False)
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    html_body: Mapped[str] = mapped_column(Text, nullable=False)
    text_body: Mapped[str] = mapped_column(Text, nullable=False)
    attachments: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_message_id: Mapped[str | None] = mapped_column(String(200))
    last_error: Mapped[str | None] = mapped_column(String(200))
    order_id: Mapped[UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"))
