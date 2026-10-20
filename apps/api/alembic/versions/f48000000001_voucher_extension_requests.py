"""Persist authenticated customer requests to extend vouchers.

Revision ID: f48000000001
Revises: aa4500000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f48000000001"
down_revision: str | None = "aa4500000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "voucher_extension_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("voucher_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.String(length=2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name=op.f("ck_voucher_extension_requests_valid_status"),
        ),
        sa.CheckConstraint(
            "length(message) <= 2000",
            name=op.f("ck_voucher_extension_requests_message_length"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"],
            name=op.f("fk_voucher_extension_requests_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["voucher_id"], ["vouchers.id"],
            name=op.f("fk_voucher_extension_requests_voucher_id_vouchers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_voucher_extension_requests")),
    )
    op.create_index(
        "uq_voucher_extension_requests_pending_voucher",
        "voucher_extension_requests",
        ["voucher_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        op.f("ix_voucher_extension_requests_customer_created"),
        "voucher_extension_requests",
        ["customer_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_voucher_extension_requests_customer_created"),
        table_name="voucher_extension_requests",
    )
    op.drop_index(
        "uq_voucher_extension_requests_pending_voucher",
        table_name="voucher_extension_requests",
    )
    op.drop_table("voucher_extension_requests")
