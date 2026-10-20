"""Persistence model for non-secret, operator-editable application settings."""

from typing import Any

from sqlalchemy import CheckConstraint, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from sensoria.database import Base, TimestampMixin, UUIDMixin


class AppSetting(UUIDMixin, TimestampMixin, Base):
    """One named JSON setting; secrets remain in environment configuration."""

    __tablename__ = "app_settings"
    __table_args__ = (
        UniqueConstraint("key"),
        CheckConstraint("length(btrim(key)) > 0", name="nonempty_key"),
    )

    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[Any] = mapped_column(JSONB(none_as_null=False), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
