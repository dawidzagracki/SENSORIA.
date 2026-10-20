"""Payment attempts and processed provider events."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from sensoria.database import Base, TimestampMixin, UUIDMixin
from sensoria.shared.types import Money

PAYMENT_STATUSES = ("pending", "succeeded", "failed", "expired", "amount_mismatch")


class Payment(UUIDMixin, TimestampMixin, Base):
    """One hosted-checkout attempt; an order may have several attempts but one pending."""

    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("provider", "provider_session_id"),
        CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed', 'expired', 'amount_mismatch')",
            name="valid_status",
        ),
        CheckConstraint("amount_grosz >= 0", name="nonnegative_amount"),
        CheckConstraint("attempt > 0", name="positive_attempt"),
        Index(
            "uq_payments_one_pending_per_order",
            "order_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_payments_order_created", "order_id", "created_at"),
    )

    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False, server_default="stripe")
    provider_session_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_payment_intent_id: Mapped[str | None] = mapped_column(String(255))
    checkout_url: Mapped[str | None] = mapped_column(String(2048))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    method: Mapped[str] = mapped_column(String(30), nullable=False)
    amount_grosz: Mapped[int] = mapped_column(Money(), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="PLN")
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    failure_code: Mapped[str | None] = mapped_column(String(100))
    session_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PaymentEvent(UUIDMixin, Base):
    """Provider event ledger; the unique event id makes webhook delivery idempotent."""

    __tablename__ = "payment_events"
    __table_args__ = (
        UniqueConstraint("provider", "provider_event_id"),
        Index("ix_payment_events_received", "received_at"),
    )

    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payment_id: Mapped[UUID | None] = mapped_column(ForeignKey("payments.id", ondelete="SET NULL"))
    outcome: Mapped[str] = mapped_column(String(40), nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
