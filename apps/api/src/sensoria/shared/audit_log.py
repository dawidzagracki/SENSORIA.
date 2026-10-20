"""Append-only audit event persistence model without domain-table foreign keys."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from sensoria.database import Base, UUIDMixin


class ActorType(StrEnum):
    """Stable actor categories persisted as English text values."""

    CUSTOMER = "customer"
    ADMINISTRATOR = "administrator"
    SYSTEM = "system"


class ActorTypeType(TypeDecorator[ActorType]):
    """Store validated actor categories as ordinary text, not a DB enum."""

    impl = String(20)
    cache_ok = True

    def process_bind_param(self, value: ActorType | None, dialect: Dialect) -> str | None:
        del dialect
        if value is None:
            return None
        if not isinstance(value, ActorType):
            raise TypeError("Typ aktora musi być wartością ActorType.")
        return value.value

    def process_result_value(self, value: Any, dialect: Dialect) -> ActorType | None:
        del dialect
        if value is None:
            return None
        try:
            return ActorType(value)
        except ValueError:
            raise ValueError("Nieznana wartość typu aktora.") from None


class AuditLog(UUIDMixin, Base):
    """Audit event with polymorphic entity reference and JSONB payload."""

    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('customer', 'administrator', 'system')",
            name="valid_actor_type",
        ),
        CheckConstraint("length(btrim(entity_type)) > 0", name="nonempty_entity_type"),
        CheckConstraint("length(btrim(action)) > 0", name="nonempty_action"),
        Index("ix_audit_log_actor_created_at", "actor_type", "actor_id", "created_at"),
        Index("ix_audit_log_entity_created_at", "entity_type", "entity_id", "created_at"),
        Index("ix_audit_log_action_created_at", "action", "created_at"),
        Index("ix_audit_log_payload", "payload", postgresql_using="gin"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actor_type: Mapped[ActorType] = mapped_column(ActorTypeType(), nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[Any] = mapped_column(JSONB(none_as_null=False), nullable=False)
