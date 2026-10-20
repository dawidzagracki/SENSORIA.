"""Order notes and the voucher event ledger.

Revision ID: f66000000001
Revises: f65000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f66000000001"
down_revision: str | None = "f65000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "order_notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("admin_id", sa.Uuid(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_notes")),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name=op.f("fk_order_notes_order_id_orders"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["admin_id"], ["admin_users.id"], name=op.f("fk_order_notes_admin_id_admin_users"), ondelete="SET NULL"
        ),
        sa.CheckConstraint("length(btrim(body)) > 0", name=op.f("ck_order_notes_nonempty_body")),
    )
    op.create_index("ix_order_notes_order_created", "order_notes", ["order_id", "created_at"])
    op.create_table(
        "voucher_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("voucher_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("admin_id", sa.Uuid(), nullable=True),
        sa.Column("performed_by", sa.String(200), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("new_valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_voucher_events")),
        sa.ForeignKeyConstraint(
            ["voucher_id"], ["vouchers.id"], name=op.f("fk_voucher_events_voucher_id_vouchers"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["admin_id"], ["admin_users.id"], name=op.f("fk_voucher_events_admin_id_admin_users"), ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            "action IN ('redeemed', 'redemption_reverted', 'cancelled', 'extended')",
            name=op.f("ck_voucher_events_valid_action"),
        ),
    )
    op.create_index("ix_voucher_events_voucher_created", "voucher_events", ["voucher_id", "created_at"])
    op.create_index("ix_voucher_events_created", "voucher_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("voucher_events")
    op.drop_table("order_notes")
