"""Product reviews and review requests.

Revision ID: f68000000001
Revises: f67000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f68000000001"
down_revision: str | None = "f67000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("order_item_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("author_name", sa.String(80), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(120), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(10), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("moderated_by", sa.Uuid(), nullable=True),
        sa.Column("moderation_note", sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reviews")),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], name=op.f("fk_reviews_product_id_products"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"], name=op.f("fk_reviews_order_item_id_order_items"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name=op.f("fk_reviews_order_id_orders"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], name=op.f("fk_reviews_customer_id_customers"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["moderated_by"], ["admin_users.id"], name=op.f("fk_reviews_moderated_by_admin_users"), ondelete="SET NULL"),
        sa.UniqueConstraint("order_item_id", name=op.f("uq_reviews_order_item_id")),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name=op.f("ck_reviews_valid_rating")),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name=op.f("ck_reviews_valid_status")),
        sa.CheckConstraint("length(btrim(body)) >= 10", name=op.f("ck_reviews_body_min_length")),
        sa.CheckConstraint("length(body) <= 2000", name=op.f("ck_reviews_body_max_length")),
    )
    op.create_index("ix_reviews_product_status_created", "reviews", ["product_id", "status", "created_at"])
    op.create_index("ix_reviews_status_created", "reviews", ["status", "created_at"])
    op.create_table(
        "review_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_item_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_requests")),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"], name=op.f("fk_review_requests_order_item_id_order_items"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name=op.f("fk_review_requests_order_id_orders"), ondelete="CASCADE"),
        sa.UniqueConstraint("order_item_id", name=op.f("uq_review_requests_order_item_id")),
    )


def downgrade() -> None:
    op.drop_table("review_requests")
    op.drop_table("reviews")
