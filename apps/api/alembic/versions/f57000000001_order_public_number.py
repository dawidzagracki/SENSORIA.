"""Add stable public order references for customer history [57].

Revision ID: f57000000001
Revises: f56000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f57000000001"
down_revision: str | None = "f56000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("public_number", sa.String(length=32), nullable=True))
    op.execute(
        "UPDATE orders SET public_number = 'SEN-' || to_char(created_at AT TIME ZONE 'Europe/Warsaw', 'YYYY') || '-' || upper(substr(replace(id::text, '-', ''), 1, 16))"
    )
    op.create_unique_constraint("uq_orders_public_number", "orders", ["public_number"])


def downgrade() -> None:
    op.drop_constraint("uq_orders_public_number", "orders", type_="unique")
    op.drop_column("orders", "public_number")
