"""Customer authentication, sessions, attempts and encrypted mail intents.

Revision ID: f54000000001
Revises: f52000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f54000000001"
down_revision: str | None = "f52000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(40)),
        sa.Column("email_verified_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("email = lower(btrim(email))", name="ck_customers_normalized_email"),
        sa.PrimaryKeyConstraint("id", name="pk_customers"),
        sa.UniqueConstraint("email", name="uq_customers_email"),
    )
    op.create_table(
        "account_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("secret_hash", sa.String(64), nullable=False),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("remember_me", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            ondelete="CASCADE",
            name="fk_account_sessions_customer_id_customers",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_account_sessions"),
        sa.UniqueConstraint("secret_hash", name="uq_account_sessions_secret_hash"),
    )
    op.create_index(
        "ix_account_sessions_customer", "account_sessions", ["customer_id", "revoked_at"]
    )
    op.create_table(
        "account_action_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("selector", sa.String(32), nullable=False),
        sa.Column("secret_hash", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(24), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "purpose IN ('password_reset', 'email_verification')",
            name="ck_account_action_tokens_valid_purpose",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            ondelete="CASCADE",
            name="fk_account_action_tokens_customer_id_customers",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_account_action_tokens"),
        sa.UniqueConstraint(
            "selector", "purpose", name="uq_account_action_tokens_selector_purpose"
        ),
    )
    op.create_index(
        "ix_account_action_tokens_lookup", "account_action_tokens", ["selector", "purpose"]
    )
    op.create_table(
        "auth_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.String(8), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True)),
        sa.CheckConstraint("scope IN ('email', 'ip')", name="ck_auth_attempts_valid_scope"),
        sa.CheckConstraint("failed_count >= 0", name="ck_auth_attempts_nonnegative_count"),
        sa.PrimaryKeyConstraint("id", name="pk_auth_attempts"),
        sa.UniqueConstraint("scope", "key_hash", name="uq_auth_attempts_scope_key_hash"),
    )
    op.create_table(
        "auth_email_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose", sa.String(24), nullable=False),
        sa.Column("payload_ciphertext", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("status", sa.String(16), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("queued_at", sa.DateTime(timezone=True)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("failure_code", sa.String(80)),
        sa.CheckConstraint(
            "status IN ('pending', 'queued', 'sent', 'failed', 'cancelled')",
            name="ck_auth_email_jobs_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            ondelete="CASCADE",
            name="fk_auth_email_jobs_customer_id_customers",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_email_jobs"),
        sa.UniqueConstraint("idempotency_key", name="uq_auth_email_jobs_idempotency_key"),
    )
    op.create_index(
        "ix_auth_email_jobs_status_created", "auth_email_jobs", ["status", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_auth_email_jobs_status_created", table_name="auth_email_jobs")
    op.drop_table("auth_email_jobs")
    op.drop_table("auth_attempts")
    op.drop_index("ix_account_action_tokens_lookup", table_name="account_action_tokens")
    op.drop_table("account_action_tokens")
    op.drop_index("ix_account_sessions_customer", table_name="account_sessions")
    op.drop_table("account_sessions")
    op.drop_table("customers")
