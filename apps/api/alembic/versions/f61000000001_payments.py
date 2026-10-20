"""Payments and payment events for Stripe hosted checkout.

Revision ID: f61000000001
Revises: f60000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f61000000001"
down_revision: str | None = "f60000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(20), server_default="stripe", nullable=False),
        sa.Column("provider_session_id", sa.String(255), nullable=False),
        sa.Column("provider_payment_intent_id", sa.String(255), nullable=True),
        sa.Column("checkout_url", sa.String(2048), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("method", sa.String(30), nullable=False),
        sa.Column("amount_grosz", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), server_default="PLN", nullable=False),
        sa.Column("attempt", sa.Integer(), server_default="1", nullable=False),
        sa.Column("failure_code", sa.String(100), nullable=True),
        sa.Column("session_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments")),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name=op.f("fk_payments_order_id_orders"), ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("provider", "provider_session_id", name=op.f("uq_payments_provider")),
        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed', 'expired', 'amount_mismatch')",
            name=op.f("ck_payments_valid_status"),
        ),
        sa.CheckConstraint("amount_grosz >= 0", name=op.f("ck_payments_nonnegative_amount")),
        sa.CheckConstraint("attempt > 0", name=op.f("ck_payments_positive_attempt")),
    )
    op.create_index(
        "uq_payments_one_pending_per_order",
        "payments",
        ["order_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index("ix_payments_order_created", "payments", ["order_id", "created_at"])
    op.create_table(
        "payment_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=True),
        sa.Column("outcome", sa.String(40), nullable=False),
        sa.Column("summary", postgresql.JSONB(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_events")),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name=op.f("fk_payment_events_payment_id_payments"),
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "provider", "provider_event_id", name=op.f("uq_payment_events_provider")
        ),
    )
    op.create_index("ix_payment_events_received", "payment_events", ["received_at"])


def downgrade() -> None:
    op.drop_table("payment_events")
    op.drop_table("payments")
