"""Expose physical-book inventory and fulfillment, plus audiobook format.

Revision ID: e920_product_media
Revises: b16f0a9c7d31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e920_product_media"
down_revision: str | None = "b16f0a9c7d31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("product_book", sa.Column("binding", sa.String(length=80), nullable=True))
    op.add_column(
        "product_book", sa.Column("shipping_business_days", sa.Integer(), nullable=True)
    )
    op.add_column(
        "product_book", sa.Column("shipping_method", sa.String(length=120), nullable=True)
    )
    op.create_check_constraint(
        "positive_shipping_days",
        "product_book",
        "shipping_business_days IS NULL OR shipping_business_days > 0",
    )
    op.create_check_constraint(
        "nonempty_shipping_method",
        "product_book",
        "shipping_method IS NULL OR length(btrim(shipping_method)) > 0",
    )
    op.add_column(
        "product_audiobook", sa.Column("file_format", sa.String(length=30), nullable=True)
    )
    op.create_check_constraint(
        "nonempty_file_format",
        "product_audiobook",
        "file_format IS NULL OR length(btrim(file_format)) > 0",
    )


def downgrade() -> None:
    op.drop_constraint("nonempty_file_format", "product_audiobook", type_="check")
    op.drop_column("product_audiobook", "file_format")
    op.drop_constraint("nonempty_shipping_method", "product_book", type_="check")
    op.drop_constraint("positive_shipping_days", "product_book", type_="check")
    op.drop_column("product_book", "shipping_method")
    op.drop_column("product_book", "shipping_business_days")
    op.drop_column("product_book", "binding")
