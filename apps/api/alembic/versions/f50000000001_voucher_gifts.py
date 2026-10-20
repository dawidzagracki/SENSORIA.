"""Persist per-line gift instructions and durable voucher delivery intents.

Revision ID: f50000000001
Revises: f49000000001
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f50000000001"
down_revision: str | None = "f49000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("cart_items", sa.Column("gift_data", postgresql.JSONB(), nullable=True))
    op.add_column("order_items", sa.Column("gift_snapshot", postgresql.JSONB(), nullable=True))
    op.add_column("vouchers", sa.Column("recipient_name", sa.String(length=160), nullable=True))
    op.add_column("vouchers", sa.Column("dedication", sa.String(length=300), nullable=True))
    op.add_column(
        "vouchers", sa.Column("gift_delivery_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("vouchers", sa.Column("gift_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "vouchers",
        sa.Column(
            "gift_delivery_status", sa.String(length=20), server_default="not_gift", nullable=False
        ),
    )
    op.add_column(
        "vouchers", sa.Column("gift_version", sa.Integer(), server_default="1", nullable=False)
    )
    op.create_check_constraint(
        "ck_vouchers_valid_gift_delivery_status",
        "vouchers",
        "gift_delivery_status IN ("
        "'not_gift', 'scheduled', 'pending', 'preparing', 'sent', 'retry', 'cancelled', 'blocked')",
    )
    op.create_check_constraint("ck_vouchers_positive_gift_version", "vouchers", "gift_version > 0")
    op.create_table(
        "voucher_gift_delivery_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("voucher_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("gift_version", sa.Integer(), nullable=False),
        sa.Column("deliver_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recipient_email", sa.String(length=320), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("queue_message_id", sa.String(length=200), nullable=True),
        sa.Column("provider_message_id", sa.String(length=200), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "gift_version > 0", name=op.f("ck_voucher_gift_delivery_jobs_positive_gift_version")
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'queued', 'sending', 'sent', 'retry', 'cancelled', 'blocked')",
            name=op.f("ck_voucher_gift_delivery_jobs_valid_status"),
        ),
        sa.ForeignKeyConstraint(
            ["voucher_id"],
            ["vouchers.id"],
            ondelete="CASCADE",
            name=op.f("fk_voucher_gift_delivery_jobs_voucher_id_vouchers"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_voucher_gift_delivery_jobs")),
        sa.UniqueConstraint(
            "voucher_id", "gift_version", name=op.f("uq_voucher_gift_delivery_jobs_voucher_version")
        ),
    )
    op.create_index(
        op.f("ix_voucher_gift_delivery_dispatch"),
        "voucher_gift_delivery_jobs",
        ["status", "deliver_at"],
    )
    op.get_bind().execute(
        sa.text(
            "INSERT INTO app_settings (id, key, value, description) "
            "VALUES (:id, 'vouchers.gifts.v1', CAST(:value AS jsonb), :description) "
            "ON CONFLICT (key) DO NOTHING"
        ),
        {
            "id": uuid4(),
            "value": '{"local_send_time":"09:00","timezone":"Europe/Warsaw",'
            '"dedication_max_length":300}',
            "description": "Planowana wysyłka prezentowych voucherów; zmiana wymaga "
            "integracji administracyjnej.",
        },
    )


def downgrade() -> None:
    op.execute("DELETE FROM app_settings WHERE key = 'vouchers.gifts.v1'")
    op.drop_index(
        op.f("ix_voucher_gift_delivery_dispatch"), table_name="voucher_gift_delivery_jobs"
    )
    op.drop_table("voucher_gift_delivery_jobs")
    op.drop_constraint("ck_vouchers_positive_gift_version", "vouchers", type_="check")
    op.drop_constraint("ck_vouchers_valid_gift_delivery_status", "vouchers", type_="check")
    op.drop_column("vouchers", "gift_version")
    op.drop_column("vouchers", "gift_delivery_status")
    op.drop_column("vouchers", "gift_sent_at")
    op.drop_column("vouchers", "gift_delivery_at")
    op.drop_column("vouchers", "dedication")
    op.drop_column("vouchers", "recipient_name")
    op.drop_column("order_items", "gift_snapshot")
    op.drop_column("cart_items", "gift_data")
