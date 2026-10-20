"""Persist the selected delivery method on a cart.

Revision ID: f32000000001
Revises: d26000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f32000000001"
down_revision: str | None = "d26000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("carts", sa.Column("delivery_method", sa.String(length=24), nullable=True))
    op.create_check_constraint(
        op.f("ck_carts_valid_delivery_method"),
        "carts",
        "delivery_method IS NULL OR delivery_method IN ('parcel_locker', 'courier')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_carts_valid_delivery_method"), "carts", type_="check")
    op.drop_column("carts", "delivery_method")
