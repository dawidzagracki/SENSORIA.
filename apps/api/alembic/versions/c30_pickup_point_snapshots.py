"""Store verified InPost pickup-point snapshots on carts and orders.

Revision ID: c30_pickup_point_snapshots
Revises: a29000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c30_pickup_point_snapshots"
down_revision: str | None = "a29000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "carts",
        sa.Column(
            "delivery_point_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "delivery_point_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("orders", "delivery_point_snapshot")
    op.drop_column("carts", "delivery_point_snapshot")
