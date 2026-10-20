"""Add guest checkout orders, immutable line snapshots, consents and stock holds.

Revision ID: a29000000001
Revises: f32000000001
"""

import json
from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a29000000001"
down_revision: str | None = "f32000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSENT_KEY = "orders.checkout.consents.v1"


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("cart_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("payment_method", sa.String(30), nullable=False),
        sa.Column("status", sa.String(24), server_default="pending_payment", nullable=False),
        sa.Column("invoice_data", postgresql.JSONB(), nullable=False),
        sa.Column("shipping_data", postgresql.JSONB(), nullable=True),
        sa.Column("calculation_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("amount_due_grosz", sa.BigInteger(), nullable=False),
        sa.Column("discount_code_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, default=uuid4),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('pending_payment', 'paid', 'cancelled', 'expired')",
            name=op.f("ck_orders_valid_status"),
        ),
        sa.CheckConstraint("length(btrim(email)) > 0", name=op.f("ck_orders_nonempty_email")),
        sa.CheckConstraint("amount_due_grosz >= 0", name=op.f("ck_orders_nonnegative_amount_due")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
        sa.ForeignKeyConstraint(
            ["cart_id"], ["carts.id"], name=op.f("fk_orders_cart_id_carts"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["discount_code_id"],
            ["discount_codes.id"],
            name=op.f("fk_orders_discount_code_id_discount_codes"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("cart_id", name=op.f("uq_orders_cart_id")),
    )
    op.create_index("ix_orders_status_created_at", "orders", ["status", "created_at"])
    op.create_table(
        "order_items",
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_snapshot", sa.BigInteger(), nullable=False),
        sa.Column("vat_rate_snapshot", sa.String(16), nullable=False),
        sa.Column("item_settlement", postgresql.JSONB(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, default=uuid4),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_order_items_positive_quantity")),
        sa.CheckConstraint(
            "vat_rate_snapshot IN ('RATE_23','RATE_8','RATE_5','RATE_0','EXEMPT')",
            name="ck_order_items_valid_vat_rate",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_items")),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_items_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_order_items_product_id_products"),
            ondelete="RESTRICT",
        ),
    )
    op.create_table(
        "order_consents",
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("displayed_text", sa.Text(), nullable=False),
        sa.Column("scope", postgresql.JSONB(), nullable=False),
        sa.Column("issuance_mode", sa.String(24), nullable=True),
        sa.Column(
            "recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, default=uuid4),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_consents")),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_consents_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("order_id", "kind", name=op.f("uq_order_consents_order_id")),
    )
    op.create_table(
        "stock_reservations",
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, default=uuid4),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_stock_reservations_positive_quantity")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_reservations")),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_stock_reservations_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_stock_reservations_product_id_products"),
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_stock_reservations_expiry", "stock_reservations", ["expires_at"])
    op.create_index(
        "ix_stock_reservations_product_expiry", "stock_reservations", ["product_id", "expires_at"]
    )
    op.create_table(
        "discount_use_reservations",
        sa.Column("discount_code_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, default=uuid4),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_discount_use_reservations")),
        sa.ForeignKeyConstraint(
            ["discount_code_id"],
            ["discount_codes.id"],
            name=op.f("fk_discount_use_reservations_discount_code_id_discount_codes"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_discount_use_reservations_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("order_id", name=op.f("uq_discount_use_reservations_order_id")),
    )
    op.create_index(
        "ix_discount_use_reservations_code_expiry",
        "discount_use_reservations",
        ["discount_code_id", "expires_at"],
    )

    # Approved wording is versioned and operator-editable in app_settings.
    consent_value = {
        "version": "checkout-v1",
        "terms": "Akceptuję regulamin i politykę prywatności.",
        "digital": (
            "Żądam udostępnienia treści cyfrowej przed upływem terminu odstąpienia od umowy. "
            "Potwierdzam otrzymanie informacji, że po spełnieniu świadczenia utracę prawo "
            "do odstąpienia od umowy."
        ),
        "marketing": (
            "Chcę dostawać wiadomość raz w miesiącu o nowych materiałach. Zgoda jest dobrowolna."
        ),
    }
    connection = op.get_bind()
    existing = connection.execute(
        sa.text("SELECT 1 FROM app_settings WHERE key = :key"), {"key": CONSENT_KEY}
    ).scalar()
    if existing is None:
        connection.execute(
            sa.text(
                "INSERT INTO app_settings (id, key, value, description) "
                "VALUES (:id, :key, CAST(:value AS jsonb), :description)"
            ),
            {
                "id": str(uuid4()),
                "key": CONSENT_KEY,
                "value": json.dumps(consent_value, ensure_ascii=False),
                "description": "Wersjonowane treści oświadczeń checkoutu.",
            },
        )

    # DiscountRedemption existed before orders; add the now-valid historical reference.
    op.create_foreign_key(
        op.f("fk_discount_redemptions_order_id_orders"),
        "discount_redemptions",
        "orders",
        ["order_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_discount_redemptions_order_id_orders"), "discount_redemptions", type_="foreignkey"
    )
    # Keep the versioned copy in app_settings; an operator may already have edited it.
    op.drop_index(
        "ix_discount_use_reservations_code_expiry", table_name="discount_use_reservations"
    )
    op.drop_table("discount_use_reservations")
    op.drop_index("ix_stock_reservations_product_expiry", table_name="stock_reservations")
    op.drop_index("ix_stock_reservations_expiry", table_name="stock_reservations")
    op.drop_table("stock_reservations")
    op.drop_table("order_consents")
    op.drop_table("order_items")
    op.drop_index("ix_orders_status_created_at", table_name="orders")
    op.drop_table("orders")
