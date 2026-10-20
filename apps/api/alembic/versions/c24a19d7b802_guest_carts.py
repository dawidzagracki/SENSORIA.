"""Add persistent guest and account cart storage.

Revision ID: c24a19d7b802
Revises: f021_product_samples
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c24a19d7b802"
down_revision: str | None = "f021_product_samples"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "carts",
        sa.Column("session_token_hash", sa.String(length=64), nullable=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(
            "(customer_id IS NULL AND session_token_hash IS NOT NULL AND expires_at IS NOT NULL) "
            "OR (customer_id IS NOT NULL AND session_token_hash IS NULL)",
            name=op.f("ck_carts_guest_or_customer_identity"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_carts")),
        sa.UniqueConstraint("session_token_hash", name=op.f("uq_carts_session_token_hash")),
    )
    op.create_index(
        "ix_carts_guest_expiry",
        "carts",
        ["expires_at"],
        unique=False,
        postgresql_where=sa.text("customer_id IS NULL"),
    )
    op.create_index(
        "uq_carts_customer_id",
        "carts",
        ["customer_id"],
        unique=True,
        postgresql_where=sa.text("customer_id IS NOT NULL"),
    )
    op.create_table(
        "cart_items",
        sa.Column("cart_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("line_key", sa.String(length=100), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_snapshot", sa.BigInteger(), nullable=False),
        sa.Column("vat_rate_snapshot", sa.String(length=16), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_cart_items_positive_quantity")),
        sa.CheckConstraint(
            "length(btrim(line_key)) > 0", name=op.f("ck_cart_items_nonempty_line_key")
        ),
        sa.CheckConstraint(
            "unit_price_snapshot >= 0", name=op.f("ck_cart_items_nonnegative_price_snapshot")
        ),
        sa.CheckConstraint(
            "vat_rate_snapshot IN ('RATE_23', 'RATE_8', 'RATE_5', 'RATE_0', 'EXEMPT')",
            name=op.f("ck_cart_items_valid_vat_rate_snapshot"),
        ),
        sa.ForeignKeyConstraint(
            ["cart_id"], ["carts.id"], name=op.f("fk_cart_items_cart_id_carts"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_cart_items_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["product_voucher_variants.id"],
            name=op.f("fk_cart_items_variant_id_product_voucher_variants"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cart_items")),
        sa.UniqueConstraint("cart_id", "line_key", name="uq_cart_items_cart_line_key"),
    )
    op.create_index("ix_cart_items_product_id", "cart_items", ["product_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_cart_items_product_id", table_name="cart_items")
    op.drop_table("cart_items")
    op.drop_index("uq_carts_customer_id", table_name="carts")
    op.drop_index("ix_carts_guest_expiry", table_name="carts")
    op.drop_table("carts")
