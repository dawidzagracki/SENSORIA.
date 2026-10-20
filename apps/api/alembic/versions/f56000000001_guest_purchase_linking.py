"""Verified-email ownership links and minimal account data adapters.

Revision ID: f56000000001
Revises: f55000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f56000000001"
down_revision: str | None = "f55000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_orders_customer_id_customers",
        "orders",
        "customers",
        ["customer_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_orders_customer_id", "orders", ["customer_id"])

    op.create_table(
        "customer_addresses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_name", sa.String(length=200)),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("address_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            ondelete="CASCADE",
            name="fk_customer_addresses_customer_id_customers",
        ),
        sa.ForeignKeyConstraint(
            ["source_order_id"],
            ["orders.id"],
            ondelete="RESTRICT",
            name="fk_customer_addresses_source_order_id_orders",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_customer_addresses"),
        sa.UniqueConstraint(
            "customer_id", "fingerprint", name="uq_customer_addresses_customer_id_fingerprint"
        ),
    )
    op.create_index("ix_customer_addresses_customer", "customer_addresses", ["customer_id"])

    op.create_table(
        "customer_billing_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=12), nullable=False),
        sa.Column("first_name", sa.String(length=100)),
        sa.Column("last_name", sa.String(length=100)),
        sa.Column("company_name", sa.String(length=200)),
        sa.Column("nip", sa.String(length=10)),
        sa.Column("address_snapshot", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "kind IN ('private', 'company')", name="ck_customer_billing_profiles_valid_kind"
        ),
        sa.CheckConstraint(
            "nip IS NULL OR nip ~ '^[0-9]{10}$'", name="ck_customer_billing_profiles_valid_nip"
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            ondelete="CASCADE",
            name="fk_customer_billing_profiles_customer_id_customers",
        ),
        sa.ForeignKeyConstraint(
            ["source_order_id"],
            ["orders.id"],
            ondelete="RESTRICT",
            name="fk_customer_billing_profiles_source_order_id_orders",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_customer_billing_profiles"),
        sa.UniqueConstraint(
            "customer_id", "kind", name="uq_customer_billing_profiles_customer_id_kind"
        ),
    )
    op.create_index(
        "ix_customer_billing_profiles_customer", "customer_billing_profiles", ["customer_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_customer_billing_profiles_customer", table_name="customer_billing_profiles")
    op.drop_table("customer_billing_profiles")
    op.drop_index("ix_customer_addresses_customer", table_name="customer_addresses")
    op.drop_table("customer_addresses")
    op.drop_index("ix_orders_customer_id", table_name="orders")
    op.drop_constraint("fk_orders_customer_id_customers", "orders", type_="foreignkey")
    op.drop_column("orders", "customer_id")
