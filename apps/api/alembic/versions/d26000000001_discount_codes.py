"""Add discount codes, cart assignment, and paid-use idempotency records.

Revision ID: d26000000001
Revises: c24a19d7b802
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d26000000001"
down_revision: str | None = "c24a19d7b802"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "discount_codes",
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("value", sa.BigInteger(), nullable=False),
        sa.Column("min_order_value", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("used_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, default=uuid4),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("length(btrim(code)) > 0", name=op.f("ck_discount_codes_nonempty_code")),
        sa.CheckConstraint(
            "type IN ('percentage', 'fixed_amount')", name=op.f("ck_discount_codes_valid_type")
        ),
        sa.CheckConstraint(
            "(type = 'percentage' AND value BETWEEN 1 AND 100) OR "
            "(type = 'fixed_amount' AND value > 0)",
            name=op.f("ck_discount_codes_valid_value"),
        ),
        sa.CheckConstraint(
            "min_order_value >= 0", name=op.f("ck_discount_codes_nonnegative_minimum")
        ),
        sa.CheckConstraint(
            "used_count >= 0", name=op.f("ck_discount_codes_nonnegative_used_count")
        ),
        sa.CheckConstraint(
            "max_uses IS NULL OR max_uses > 0", name=op.f("ck_discount_codes_positive_max_uses")
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to > valid_from",
            name=op.f("ck_discount_codes_valid_dates"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_discount_codes")),
    )
    op.create_index(
        "uq_discount_codes_normalized_code",
        "discount_codes",
        [sa.text("lower(btrim(code))")],
        unique=True,
    )
    op.add_column(
        "carts", sa.Column("discount_code_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        op.f("fk_carts_discount_code_id_discount_codes"),
        "carts",
        "discount_codes",
        ["discount_code_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_table(
        "discount_redemptions",
        sa.Column("discount_code_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, default=uuid4),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_discount_redemptions")),
        sa.ForeignKeyConstraint(
            ["discount_code_id"],
            ["discount_codes.id"],
            name=op.f("fk_discount_redemptions_discount_code_id_discount_codes"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "discount_code_id", "order_id", name=op.f("uq_discount_redemptions_discount_code_id")
        ),
    )


def downgrade() -> None:
    op.drop_table("discount_redemptions")
    op.drop_constraint(
        op.f("fk_carts_discount_code_id_discount_codes"), "carts", type_="foreignkey"
    )
    op.drop_column("carts", "discount_code_id")
    op.drop_index("uq_discount_codes_normalized_code", table_name="discount_codes")
    op.drop_table("discount_codes")
