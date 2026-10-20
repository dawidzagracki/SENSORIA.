"""Persist voucher reminder cycles and bounded scheduler run summaries.

Revision ID: f49000000001
Revises: f48000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f49000000001"
down_revision: str | None = "f48000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "voucher_reminders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("voucher_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("valid_until_snapshot", sa.DateTime(timezone=True), nullable=False),
        sa.Column("threshold_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="blocked", nullable=False),
        sa.Column("skip_reason", sa.String(length=80), nullable=True),
        sa.Column("queue_message_id", sa.String(length=200), nullable=True),
        sa.Column("provider_message_id", sa.String(length=200), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("retry_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "threshold_days > 0", name=op.f("ck_voucher_reminders_positive_threshold_days")
        ),
        sa.CheckConstraint(
            "status IN ('blocked', 'queued', 'sent', 'skipped', 'cancelled', 'failed')",
            name=op.f("ck_voucher_reminders_valid_status"),
        ),
        sa.CheckConstraint(
            "sent_at IS NULL OR status = 'sent'",
            name=op.f("ck_voucher_reminders_sent_only_after_provider_acceptance"),
        ),
        sa.ForeignKeyConstraint(
            ["voucher_id"],
            ["vouchers.id"],
            ondelete="RESTRICT",
            name=op.f("fk_voucher_reminders_voucher_id_vouchers"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_voucher_reminders")),
        sa.UniqueConstraint(
            "voucher_id",
            "valid_until_snapshot",
            "threshold_days",
            name=op.f("uq_voucher_reminders_cycle"),
        ),
        sa.UniqueConstraint("queue_message_id", name=op.f("uq_voucher_reminders_queue_message_id")),
    )
    op.create_index(
        op.f("ix_voucher_reminders_dispatch"), "voucher_reminders", ["status", "created_at"]
    )
    op.create_table(
        "voucher_reminder_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("configuration", postgresql.JSONB(), nullable=False),
        sa.Column(
            "skip_reasons",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "error_reasons",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("checked_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("qualified_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("queued_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("skipped_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("limit_reached", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("has_more", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint(
            "checked_count >= 0", name=op.f("ck_voucher_reminder_runs_nonnegative_checked")
        ),
        sa.CheckConstraint(
            "qualified_count >= 0", name=op.f("ck_voucher_reminder_runs_nonnegative_qualified")
        ),
        sa.CheckConstraint(
            "queued_count >= 0", name=op.f("ck_voucher_reminder_runs_nonnegative_queued")
        ),
        sa.CheckConstraint(
            "skipped_count >= 0", name=op.f("ck_voucher_reminder_runs_nonnegative_skipped")
        ),
        sa.CheckConstraint(
            "error_count >= 0", name=op.f("ck_voucher_reminder_runs_nonnegative_errors")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_voucher_reminder_runs")),
    )
    op.create_index(
        op.f("ix_voucher_reminder_runs_started"), "voucher_reminder_runs", ["started_at"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_voucher_reminder_runs_started"), table_name="voucher_reminder_runs")
    op.drop_table("voucher_reminder_runs")
    op.drop_index(op.f("ix_voucher_reminders_dispatch"), table_name="voucher_reminders")
    op.drop_table("voucher_reminders")
