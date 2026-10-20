"""Durable mail outbox.

Revision ID: f64000000001
Revises: f63000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f64000000001"
down_revision: str | None = "f63000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mail_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("template_key", sa.String(60), nullable=False),
        sa.Column("recipient", sa.String(320), nullable=False),
        sa.Column("subject", sa.String(300), nullable=False),
        sa.Column("html_body", sa.Text(), nullable=False),
        sa.Column("text_body", sa.Text(), nullable=False),
        sa.Column("attachments", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("status", sa.String(12), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_message_id", sa.String(200), nullable=True),
        sa.Column("last_error", sa.String(200), nullable=True),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mail_outbox")),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name=op.f("fk_mail_outbox_order_id_orders"), ondelete="SET NULL"
        ),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_mail_outbox_idempotency_key")),
        sa.CheckConstraint(
            "status IN ('pending', 'sending', 'sent', 'retry', 'failed', 'cancelled')",
            name=op.f("ck_mail_outbox_valid_status"),
        ),
        sa.CheckConstraint("attempts >= 0", name=op.f("ck_mail_outbox_nonnegative_attempts")),
    )
    op.create_index("ix_mail_outbox_dispatch", "mail_outbox", ["status", "next_attempt_at"])
    op.create_index("ix_mail_outbox_recipient", "mail_outbox", ["recipient"])


def downgrade() -> None:
    op.drop_table("mail_outbox")
