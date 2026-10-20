"""Editable customer profiles and saved delivery addresses.

Revision ID: f59000000001
Revises: f58000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f59000000001"
down_revision: str | None = "f58000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("pending_email", sa.String(320)))
    op.add_column("account_sessions", sa.Column("reauthenticated_at", sa.DateTime(timezone=True)))
    op.add_column("account_action_tokens", sa.Column("target_email", sa.String(320)))
    op.drop_constraint(
        "ck_account_action_tokens_valid_purpose", "account_action_tokens", type_="check"
    )
    op.create_check_constraint(
        "ck_account_action_tokens_valid_purpose",
        "account_action_tokens",
        "purpose IN ('password_reset', 'email_verification', 'email_change')",
    )

    op.alter_column("customer_addresses", "source_order_id", nullable=True)
    op.add_column(
        "customer_addresses",
        sa.Column("label", sa.String(80), server_default="Adres dostawy", nullable=False),
    )
    op.add_column(
        "customer_addresses",
        sa.Column("address_type", sa.String(20), server_default="address", nullable=False),
    )
    op.add_column(
        "customer_addresses",
        sa.Column("is_default", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "customer_addresses",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute(
        """
        UPDATE customer_addresses
        SET address_type = 'parcel_locker', label = 'Paczkomat z zamówienia'
        WHERE address_snapshot ? 'code'
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT id, row_number() OVER (
                PARTITION BY customer_id ORDER BY created_at, id
            ) AS row_num
            FROM customer_addresses
        )
        UPDATE customer_addresses AS addresses
        SET is_default = true, label = 'Adres z zamówienia'
        FROM ranked
        WHERE ranked.id = addresses.id AND ranked.row_num = 1
        """
    )
    op.create_check_constraint(
        "ck_customer_addresses_valid_address_type",
        "customer_addresses",
        "address_type IN ('address', 'parcel_locker')",
    )
    op.create_index(
        "uq_customer_addresses_one_default",
        "customer_addresses",
        ["customer_id"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )


def downgrade() -> None:
    op.drop_index("uq_customer_addresses_one_default", table_name="customer_addresses")
    op.drop_constraint(
        "ck_customer_addresses_valid_address_type", "customer_addresses", type_="check"
    )
    op.drop_column("customer_addresses", "updated_at")
    op.drop_column("customer_addresses", "is_default")
    op.drop_column("customer_addresses", "address_type")
    op.drop_column("customer_addresses", "label")
    op.alter_column("customer_addresses", "source_order_id", nullable=False)
    op.drop_constraint(
        "ck_account_action_tokens_valid_purpose", "account_action_tokens", type_="check"
    )
    op.create_check_constraint(
        "ck_account_action_tokens_valid_purpose",
        "account_action_tokens",
        "purpose IN ('password_reset', 'email_verification')",
    )
    op.drop_column("account_action_tokens", "target_email")
    op.drop_column("account_sessions", "reauthenticated_at")
    op.drop_column("customers", "pending_email")
