"""Voucher snapshots and durable PDF-rendering jobs."""

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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from sensoria.database import Base, TimestampMixin, UUIDMixin


class Voucher(UUIDMixin, TimestampMixin, Base):
    """One issued service voucher per purchased order-item unit."""

    __tablename__ = "vouchers"
    __table_args__ = (
        UniqueConstraint("code"),
        UniqueConstraint("order_item_id", "unit_index"),
        CheckConstraint("unit_index >= 0", name="nonnegative_unit_index"),
        CheckConstraint(
            "status IN ('active', 'redeemed', 'expired', 'cancelled')", name="valid_status"
        ),
        CheckConstraint("valid_until > issued_at", name="valid_validity"),
        Index("ix_vouchers_product_status_valid_until", "product_id", "status", "valid_until"),
    )

    code: Mapped[str] = mapped_column(String(13), nullable=False)
    order_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("order_items.id", ondelete="RESTRICT"), nullable=False
    )
    unit_index: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    variant: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    redeemed_by: Mapped[str | None] = mapped_column(String(200))
    pdf_file_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("stored_files.id", ondelete="SET NULL")
    )
    recipient_email: Mapped[str | None] = mapped_column(String(320))
    issue_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    recipient_name: Mapped[str | None] = mapped_column(String(160))
    dedication: Mapped[str | None] = mapped_column(String(300))
    gift_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gift_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gift_delivery_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="not_gift"
    )
    gift_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class VoucherPDFJob(UUIDMixin, TimestampMixin, Base):
    """Durable, idempotent work item for rendering a voucher PDF."""

    __tablename__ = "voucher_pdf_jobs"
    __table_args__ = (
        UniqueConstraint("voucher_id"),
        CheckConstraint(
            "status IN ('pending', 'processing', 'complete', 'failed')", name="valid_status"
        ),
        CheckConstraint("attempts >= 0", name="nonnegative_attempts"),
        Index("ix_voucher_pdf_jobs_dispatch", "status", "available_at"),
    )

    voucher_id: Mapped[UUID] = mapped_column(
        ForeignKey("vouchers.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))


class VoucherGiftDeliveryJob(UUIDMixin, TimestampMixin, Base):
    """Durable delivery intent; actual sending requires the missing [63] provider worker."""

    __tablename__ = "voucher_gift_delivery_jobs"
    __table_args__ = (
        UniqueConstraint(
            "voucher_id",
            "gift_version",
            name="uq_voucher_gift_delivery_jobs_voucher_version",
        ),
        CheckConstraint("gift_version > 0", name="positive_gift_version"),
        CheckConstraint(
            "status IN ('pending', 'queued', 'sending', 'sent', 'retry', 'cancelled', 'blocked')",
            name="valid_status",
        ),
        Index("ix_voucher_gift_delivery_dispatch", "status", "deliver_at"),
    )

    voucher_id: Mapped[UUID] = mapped_column(
        ForeignKey("vouchers.id", ondelete="CASCADE"), nullable=False
    )
    gift_version: Mapped[int] = mapped_column(Integer, nullable=False)
    deliver_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recipient_email: Mapped[str | None] = mapped_column(String(320))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    queue_message_id: Mapped[str | None] = mapped_column(String(200))
    provider_message_id: Mapped[str | None] = mapped_column(String(200))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))


class VoucherVerificationWindow(UUIDMixin, Base):
    """PostgreSQL-backed throttle bucket for anonymous public code checks."""

    __tablename__ = "voucher_verification_windows"
    __table_args__ = (
        UniqueConstraint("subject_hash", "window_started_at"),
        CheckConstraint("request_count >= 0", name="nonnegative_request_count"),
        Index("ix_voucher_verification_windows_expiry", "window_started_at"),
    )

    subject_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class VoucherExtensionRequest(UUIDMixin, TimestampMixin, Base):
    """Customer request awaiting an administrator's decision; never extends validity."""

    __tablename__ = "voucher_extension_requests"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="valid_status"),
        CheckConstraint("length(message) <= 2000", name="message_length"),
        Index(
            "uq_voucher_extension_requests_pending_voucher",
            "voucher_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_voucher_extension_requests_customer_created", "customer_id", "created_at"),
    )

    voucher_id: Mapped[UUID] = mapped_column(
        ForeignKey("vouchers.id", ondelete="RESTRICT"), nullable=False
    )
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )
    # Customer accounts are not implemented in this repository yet; this UUID is populated
    # only from the authenticated principal established by the future accounts integration.
    customer_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(String(2000))


class VoucherReminder(UUIDMixin, TimestampMixin, Base):
    """One reminder milestone for one immutable voucher-validity cycle."""

    __tablename__ = "voucher_reminders"
    __table_args__ = (
        UniqueConstraint(
            "voucher_id",
            "valid_until_snapshot",
            "threshold_days",
            name="uq_voucher_reminders_cycle",
        ),
        UniqueConstraint("queue_message_id"),
        CheckConstraint("threshold_days > 0", name="positive_threshold_days"),
        CheckConstraint(
            "status IN ('blocked', 'queued', 'sent', 'skipped', 'cancelled', 'failed')",
            name="valid_status",
        ),
        CheckConstraint(
            "sent_at IS NULL OR status = 'sent'", name="sent_only_after_provider_acceptance"
        ),
        Index("ix_voucher_reminders_dispatch", "status", "created_at"),
    )

    voucher_id: Mapped[UUID] = mapped_column(
        ForeignKey("vouchers.id", ondelete="RESTRICT"), nullable=False
    )
    valid_until_snapshot: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    threshold_days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="blocked")
    skip_reason: Mapped[str | None] = mapped_column(String(80))
    queue_message_id: Mapped[str | None] = mapped_column(String(200))
    provider_message_id: Mapped[str | None] = mapped_column(String(200))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    retry_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class VoucherReminderRun(UUIDMixin, Base):
    """Auditable summary of one bounded scheduler run, without customer data."""

    __tablename__ = "voucher_reminder_runs"
    __table_args__ = (
        CheckConstraint("checked_count >= 0", name="nonnegative_checked"),
        CheckConstraint("qualified_count >= 0", name="nonnegative_qualified"),
        CheckConstraint("queued_count >= 0", name="nonnegative_queued"),
        CheckConstraint("skipped_count >= 0", name="nonnegative_skipped"),
        CheckConstraint("error_count >= 0", name="nonnegative_errors"),
        Index("ix_voucher_reminder_runs_started", "started_at"),
    )

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    skip_reasons: Mapped[dict[str, int]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    error_reasons: Mapped[dict[str, int]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    checked_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    qualified_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    queued_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    limit_reached: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    has_more: Mapped[bool] = mapped_column(nullable=False, server_default="false")


class VoucherEvent(UUIDMixin, Base):
    """Append-only voucher ledger: redemption, reversal, cancellation, extension."""

    __tablename__ = "voucher_events"
    __table_args__ = (
        CheckConstraint(
            "action IN ('redeemed', 'redemption_reverted', 'cancelled', 'extended')",
            name="valid_action",
        ),
        Index("ix_voucher_events_voucher_created", "voucher_id", "created_at"),
        Index("ix_voucher_events_created", "created_at"),
    )

    voucher_id: Mapped[UUID] = mapped_column(
        ForeignKey("vouchers.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(24), nullable=False)
    admin_id: Mapped[UUID | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    performed_by: Mapped[str | None] = mapped_column(String(200))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    previous_valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    new_valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
