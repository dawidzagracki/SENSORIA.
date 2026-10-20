"""catalog_query_indexes

Revision ID: a15c0f3d2e71
Revises: f31a9d4b
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a15c0f3d2e71"
down_revision: str | None = "f31a9d4b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add indexes for the public filters and stable catalog sort paths."""

    op.create_index(
        "ix_products_status_price",
        "products",
        ["status", "price"],
        unique=False,
    )
    op.create_index(
        "ix_products_catalog_recommended",
        "products",
        ["status", "sort_order", "published_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop only indexes introduced by this revision."""

    op.drop_index("ix_products_catalog_recommended", table_name="products")
    op.drop_index("ix_products_status_price", table_name="products")
