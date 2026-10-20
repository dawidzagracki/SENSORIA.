"""Private stored-file metadata used by voucher documents."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from sensoria.database import Base, UUIDMixin


class StoredFile(UUIDMixin, Base):
    """Metadata for a private file; paths are derived from trusted fields only."""

    __tablename__ = "stored_files"
    __table_args__ = (
        CheckConstraint(
            "category IN ('vouchers', 'products', 'watermarked', 'documents')",
            name="valid_category",
        ),
        CheckConstraint("size_bytes > 0", name="positive_size"),
        CheckConstraint("length(stored_name) = 64", name="valid_stored_name"),
        Index("ix_stored_files_category_scope", "category", "scope_id"),
    )

    category: Mapped[str] = mapped_column(String(20), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_id: Mapped[UUID] = mapped_column(nullable=False)
    storage_year: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
