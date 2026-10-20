"""Allow in-person pickup as a cart delivery method.

Revision ID: f71000000001
Revises: f70000000001
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f71000000001"
down_revision: str | None = "f70000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_carts_valid_delivery_method"), "carts", type_="check")
    op.create_check_constraint(
        op.f("ck_carts_valid_delivery_method"),
        "carts",
        "delivery_method IS NULL OR delivery_method IN "
        "('parcel_locker', 'courier', 'pickup_in_person')",
    )


def downgrade() -> None:
    op.execute("UPDATE carts SET delivery_method = NULL WHERE delivery_method = 'pickup_in_person'")
    op.drop_constraint(op.f("ck_carts_valid_delivery_method"), "carts", type_="check")
    op.create_check_constraint(
        op.f("ck_carts_valid_delivery_method"),
        "carts",
        "delivery_method IS NULL OR delivery_method IN ('parcel_locker', 'courier')",
    )
