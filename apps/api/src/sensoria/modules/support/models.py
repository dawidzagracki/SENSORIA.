"""Support cases raised by buyers about a paid order."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from sensoria.database import Base, UUIDMixin


class SupportCase(UUIDMixin, Base):
    __tablename__ = "support_cases"
    __table_args__ = (
        CheckConstraint("kind IN ('withdrawal', 'return', 'complaint')", name="valid_kind"),
        CheckConstraint(
            "status IN ('new', 'in_progress', 'resolved', 'rejected')", name="valid_status"
        ),
        CheckConstraint("length(btrim(message)) >= 5", name="message_min_length"),
        Index("ix_support_cases_status_created", "status", "created_at"),
        Index("ix_support_cases_order", "order_id"),
    )

    public_number: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )
    order_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("order_items.id", ondelete="RESTRICT")
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="new")
    resolution_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    handled_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="SET NULL")
    )
