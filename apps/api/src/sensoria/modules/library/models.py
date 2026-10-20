"""Persistence for purchased digital access, downloads and reading/listening progress."""

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
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from sensoria.database import Base, TimestampMixin, UUIDMixin


class ProductFile(UUIDMixin, Base):
    """Private full-length file attached to a DIGITAL or AUDIOBOOK product."""

    __tablename__ = "product_files"
    __table_args__ = (
        CheckConstraint("kind IN ('pdf', 'audio')", name="valid_kind"),
        CheckConstraint("position >= 0", name="nonnegative_position"),
        UniqueConstraint("stored_file_id"),
        Index("ix_product_files_product_position", "product_id", "position"),
    )

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    stored_file_id: Mapped[UUID] = mapped_column(
        ForeignKey("stored_files.id", ondelete="RESTRICT"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    chapter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("product_audiobook_chapters.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EbookChapter(UUIDMixin, TimestampMixin, Base):
    """Structured reader content; blocks are data, never raw HTML."""

    __tablename__ = "ebook_chapters"
    __table_args__ = (
        UniqueConstraint("product_id", "position"),
        CheckConstraint("position >= 0", name="nonnegative_position"),
        CheckConstraint("length(btrim(title)) > 0", name="nonempty_title"),
        CheckConstraint("page_count IS NULL OR page_count > 0", name="positive_page_count"),
    )

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    blocks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)


class Entitlement(UUIDMixin, TimestampMixin, Base):
    """Right to use one purchased digital line item; created atomically with payment."""

    __tablename__ = "entitlements"
    __table_args__ = (
        UniqueConstraint("order_item_id"),
        CheckConstraint("status IN ('active', 'revoked')", name="valid_status"),
        CheckConstraint("kind IN ('digital', 'audiobook')", name="valid_kind"),
        Index("ix_entitlements_order", "order_id"),
        Index("ix_entitlements_product", "product_id"),
    )

    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )
    order_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("order_items.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="active")
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(Text)


class DownloadLink(UUIDMixin, Base):
    """Time- and use-limited link; only the keyed digest of the token is stored."""

    __tablename__ = "download_links"
    __table_args__ = (
        UniqueConstraint("token_hash"),
        CheckConstraint("max_uses > 0", name="positive_max_uses"),
        CheckConstraint("use_count >= 0", name="nonnegative_use_count"),
        Index("ix_download_links_entitlement_file", "entitlement_id", "product_file_id"),
    )

    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    entitlement_id: Mapped[UUID] = mapped_column(
        ForeignKey("entitlements.id", ondelete="CASCADE"), nullable=False
    )
    product_file_id: Mapped[UUID] = mapped_column(
        ForeignKey("product_files.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    max_uses: Mapped[int] = mapped_column(Integer, nullable=False)
    use_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class WatermarkedFile(UUIDMixin, Base):
    """Per-entitlement stamped copy of a source PDF, generated once and cached."""

    __tablename__ = "watermarked_files"
    __table_args__ = (UniqueConstraint("entitlement_id", "product_file_id"),)

    entitlement_id: Mapped[UUID] = mapped_column(
        ForeignKey("entitlements.id", ondelete="CASCADE"), nullable=False
    )
    product_file_id: Mapped[UUID] = mapped_column(
        ForeignKey("product_files.id", ondelete="CASCADE"), nullable=False
    )
    stored_file_id: Mapped[UUID] = mapped_column(
        ForeignKey("stored_files.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ContentProgress(Base):
    """Reading position (chapter) or listening position (chapter + seconds)."""

    __tablename__ = "content_progress"
    __table_args__ = (
        CheckConstraint("position >= 0", name="nonnegative_position"),
        CheckConstraint("offset_seconds >= 0", name="nonnegative_offset"),
    )

    entitlement_id: Mapped[UUID] = mapped_column(
        ForeignKey("entitlements.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    offset_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    completed: Mapped[list[int]] = mapped_column(JSONB, nullable=False, server_default="[]")
    font_scale: Mapped[int] = mapped_column(Integer, nullable=False, server_default="100")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
