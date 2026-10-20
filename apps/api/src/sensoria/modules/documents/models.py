"""Sales document persistence: gapless per-year numbering and immutable data snapshots."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from sensoria.database import Base, UUIDMixin


class DocumentCounter(Base):
    """Row-locked counter; allocation inside the issuing transaction keeps numbers gapless."""

    __tablename__ = "document_counters"
    __table_args__ = (CheckConstraint("last_number >= 0", name="nonnegative_last_number"),)

    kind: Mapped[str] = mapped_column(String(10), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class SalesDocument(UUIDMixin, Base):
    """One receipt or invoice per order; the snapshot never changes after issue."""

    __tablename__ = "sales_documents"
    __table_args__ = (
        UniqueConstraint("order_id", "kind"),
        UniqueConstraint("number"),
        CheckConstraint("kind IN ('receipt', 'invoice')", name="valid_kind"),
    )

    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    number: Mapped[str] = mapped_column(String(40), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    stored_file_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("stored_files.id", ondelete="RESTRICT")
    )
