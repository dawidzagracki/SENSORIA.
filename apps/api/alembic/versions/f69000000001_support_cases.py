"""Support cases (withdrawals, returns, complaints).

Revision ID: f69000000001
Revises: f68000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f69000000001"
down_revision: str | None = "f68000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "support_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("public_number", sa.String(32), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("order_item_id", sa.Uuid(), nullable=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(12), server_default="new", nullable=False),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("handled_by", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_support_cases")),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name=op.f("fk_support_cases_order_id_orders"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"], name=op.f("fk_support_cases_order_item_id_order_items"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["handled_by"], ["admin_users.id"], name=op.f("fk_support_cases_handled_by_admin_users"), ondelete="SET NULL"),
        sa.UniqueConstraint("public_number", name=op.f("uq_support_cases_public_number")),
        sa.CheckConstraint("kind IN ('withdrawal', 'return', 'complaint')", name=op.f("ck_support_cases_valid_kind")),
        sa.CheckConstraint("status IN ('new', 'in_progress', 'resolved', 'rejected')", name=op.f("ck_support_cases_valid_status")),
        sa.CheckConstraint("length(btrim(message)) >= 5", name=op.f("ck_support_cases_message_min_length")),
    )
    op.create_index("ix_support_cases_status_created", "support_cases", ["status", "created_at"])
    op.create_index("ix_support_cases_order", "support_cases", ["order_id"])


def downgrade() -> None:
    op.drop_table("support_cases")
