"""Customer credentials, revocable sessions and one-time account tokens."""

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
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from sensoria.database import Base, UUIDMixin


class Customer(UUIDMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (CheckConstraint("email = lower(btrim(email))", name="normalized_email"),)

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40))
    pending_email: Mapped[str | None] = mapped_column(String(320))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CustomerAddress(UUIDMixin, Base):
    """A customer's saved delivery address, including imported order destinations."""

    __tablename__ = "customer_addresses"
    __table_args__ = (
        UniqueConstraint(
            "customer_id", "fingerprint", name="uq_customer_addresses_customer_id_fingerprint"
        ),
        Index("ix_customer_addresses_customer", "customer_id"),
        CheckConstraint("address_type IN ('address', 'parcel_locker')", name="valid_address_type"),
        Index(
            "uq_customer_addresses_one_default",
            "customer_id",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )

    customer_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    source_order_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), nullable=True
    )
    label: Mapped[str] = mapped_column(String(80), nullable=False, default="Adres")
    address_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="address", server_default="address"
    )
    is_default: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    # Present in the schema since [56]; kept nullable and currently unused by the application.
    recipient_name: Mapped[str | None] = mapped_column(String(200))
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    address_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CustomerBillingProfile(UUIDMixin, Base):
    """First imported billing snapshot per account and buyer type; never overwrites edits."""

    __tablename__ = "customer_billing_profiles"
    __table_args__ = (
        UniqueConstraint(
            "customer_id", "kind", name="uq_customer_billing_profiles_customer_id_kind"
        ),
        CheckConstraint("kind IN ('private', 'company')", name="valid_kind"),
        Index("ix_customer_billing_profiles_customer", "customer_id"),
    )

    customer_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    source_order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    company_name: Mapped[str | None] = mapped_column(String(200))
    nip: Mapped[str | None] = mapped_column(String(10))
    address_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AccountSession(UUIDMixin, Base):
    __tablename__ = "account_sessions"
    __table_args__ = (Index("ix_account_sessions_customer", "customer_id", "revoked_at"),)

    customer_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    csrf_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reauthenticated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    remember_me: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")


class AccountActionToken(UUIDMixin, Base):
    __tablename__ = "account_action_tokens"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('password_reset', 'email_verification', 'email_change')",
            name="valid_purpose",
        ),
        Index("ix_account_action_tokens_lookup", "selector", "purpose"),
        UniqueConstraint("selector", "purpose", name="uq_account_action_tokens_selector_purpose"),
    )

    customer_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    selector: Mapped[str] = mapped_column(String(32), nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[str] = mapped_column(String(24), nullable=False)
    target_email: Mapped[str | None] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthAttempt(UUIDMixin, Base):
    __tablename__ = "auth_attempts"
    scope: Mapped[str] = mapped_column(String(8), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("scope IN ('email', 'ip')", name="valid_scope"),
        CheckConstraint("failed_count >= 0", name="nonnegative_count"),
        UniqueConstraint("scope", "key_hash", name="uq_auth_attempts_scope_key_hash"),
    )


class AuthEmailJob(UUIDMixin, Base):
    """Durable encrypted email intent; delivery requires the future [63] worker."""

    __tablename__ = "auth_email_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'queued', 'sent', 'failed', 'cancelled')", name="valid_status"
        ),
        Index("ix_auth_email_jobs_status_created", "status", "created_at"),
    )

    customer_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(24), nullable=False)
    payload_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(80))


class LoginLink(UUIDMixin, Base):
    """One-time passwordless login credential; only its SHA-256 digest is stored."""

    __tablename__ = "login_links"
    __table_args__ = (
        CheckConstraint("expires_at > created_at", name="positive_lifetime"),
        Index("ix_login_links_customer_created", "customer_id", "created_at"),
        Index(
            "uq_login_links_one_active_per_customer",
            "customer_id",
            unique=True,
            postgresql_where=text("used_at IS NULL AND invalidated_at IS NULL"),
        ),
    )

    customer_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_ip: Mapped[str] = mapped_column(String(64), nullable=False)
    return_to: Mapped[str] = mapped_column(Text, nullable=False, default="/konto/biblioteka")
    email_job_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("auth_email_jobs.id", ondelete="SET NULL"), unique=True
    )


class ConsentTextVersion(UUIDMixin, Base):
    """Immutable text shown when a consent event was recorded."""

    __tablename__ = "consent_text_versions"
    __table_args__ = (UniqueConstraint("consent_type", "version"),)

    consent_type: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CustomerConsent(UUIDMixin, Base):
    """Append-only consent event for an account or a verified guest email."""

    __tablename__ = "customer_consents"
    __table_args__ = (
        CheckConstraint(
            "consent_type IN ('new_materials', 'voucher_reminders', 'review_requests', "
            "'checkout_terms', 'checkout_digital', 'checkout_marketing')",
            name="valid_consent_type",
        ),
        CheckConstraint(
            "(customer_id IS NOT NULL) OR (email IS NOT NULL) OR (subject_digest IS NOT NULL)",
            name="has_subject",
        ),
        Index(
            "ix_customer_consents_account_type_time", "customer_id", "consent_type", "occurred_at"
        ),
        Index("ix_customer_consents_email_type_time", "email", "consent_type", "occurred_at"),
        UniqueConstraint("order_consent_id"),
    )

    customer_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL")
    )
    email: Mapped[str | None] = mapped_column(String(320))
    subject_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    consent_type: Mapped[str] = mapped_column(String(40), nullable=False)
    granted: Mapped[bool] = mapped_column(nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    consent_text_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("consent_text_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    order_consent_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("order_consents.id", ondelete="SET NULL")
    )


class ConsentGuestImport(UUIDMixin, Base):
    """Idempotency marker for importing checkout consent evidence to a verified account."""

    __tablename__ = "consent_guest_imports"
    __table_args__ = (UniqueConstraint("order_consent_id"),)

    order_consent_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("order_consents.id", ondelete="RESTRICT"), nullable=False
    )
    customer_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    consent_event_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("customer_consents.id", ondelete="RESTRICT"),
        nullable=False,
    )


class AccountPrivacyJob(UUIDMixin, Base):
    """Durable export/deletion workflow, processed by the accounts scheduler."""

    __tablename__ = "account_privacy_jobs"
    __table_args__ = (
        CheckConstraint("kind IN ('export', 'deletion')", name="valid_kind"),
        CheckConstraint(
            "status IN ('pending', 'processing', 'ready', 'complete', 'failed', 'cancelled')",
            name="valid_status",
        ),
        Index("ix_account_privacy_jobs_dispatch", "status", "created_at"),
        Index("ix_account_privacy_jobs_customer_created", "customer_id", "created_at"),
    )

    customer_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    file_name: Mapped[str | None] = mapped_column(String(80))
    error_code: Mapped[str | None] = mapped_column(String(80))


class DeletedEmailSuppression(UUIDMixin, Base):
    """Keyed digest preventing deleted accounts from being resurrected by relinking."""

    __tablename__ = "deleted_email_suppressions"
    email_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
