"""Persist shipment state, immutable tracking history and notification intents.

Revision ID: f52000000001
Revises: f51000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f52000000001"
down_revision: str | None = "f51000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "fulfillment_status",
            sa.String(length=24),
            server_default="awaiting_fulfillment",
            nullable=False,
        ),
    )
    op.add_column("orders", sa.Column("fulfillment_ready_at", sa.DateTime(timezone=True)))
    op.add_column("orders", sa.Column("pickup_ready_at", sa.DateTime(timezone=True)))
    op.add_column(
        "orders", sa.Column("pickup_ready_by", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column("orders", sa.Column("picked_up_at", sa.DateTime(timezone=True)))
    op.add_column("orders", sa.Column("picked_up_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_check_constraint(
        "ck_orders_valid_fulfillment_status",
        "orders",
        "fulfillment_status IN ('awaiting_fulfillment', 'shipped', 'delivered', "
        "'ready_for_pickup', 'picked_up', 'cancelled')",
    )

    op.create_table(
        "shipments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("carrier", sa.String(length=40), nullable=False),
        sa.Column("tracking_number", sa.String(length=160), nullable=False),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(length=16), server_default="shipped", nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint("length(btrim(carrier)) > 0", name="ck_shipments_nonempty_carrier"),
        sa.CheckConstraint(
            "length(btrim(tracking_number)) > 0", name="ck_shipments_nonempty_tracking_number"
        ),
        sa.CheckConstraint("status IN ('shipped', 'delivered')", name="ck_shipments_valid_status"),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], ondelete="RESTRICT", name="fk_shipments_order_id_orders"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_shipments"),
        sa.UniqueConstraint("order_id", name="uq_shipments_order_id"),
    )
    op.create_index("ix_shipments_shipped_at", "shipments", ["shipped_at"])

    op.create_table(
        "shipment_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("previous_carrier", sa.String(length=40)),
        sa.Column("new_carrier", sa.String(length=40)),
        sa.Column("previous_tracking_number", sa.String(length=160)),
        sa.Column("new_tracking_number", sa.String(length=160)),
        sa.Column(
            "changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("performed_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation", sa.String(length=16), nullable=False),
        sa.Column("operation_key", sa.String(length=120)),
        sa.Column("reason", sa.Text()),
        sa.UniqueConstraint(
            "shipment_id", "operation_key", name="uq_shipment_history_shipment_operation_key"
        ),
        sa.CheckConstraint(
            "operation IN ('created', 'corrected', 'delivered')",
            name="ck_shipment_history_valid_operation",
        ),
        sa.ForeignKeyConstraint(
            ["shipment_id"],
            ["shipments.id"],
            ondelete="RESTRICT",
            name="fk_shipment_history_shipment_id_shipments",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_shipment_history"),
    )
    op.create_index(
        "ix_shipment_history_shipment_changed", "shipment_history", ["shipment_id", "changed_at"]
    )

    op.create_table(
        "shipment_notification_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True)),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("idempotency_key", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("failed_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failure_code", sa.String(length=80)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "kind IN ('shipped', 'pickup_ready', 'manual_resend')",
            name="ck_shipment_notification_jobs_valid_kind",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'sending', 'sent', 'failed', 'cancelled')",
            name="ck_shipment_notification_jobs_valid_status",
        ),
        sa.CheckConstraint(
            "attempts >= 0", name="ck_shipment_notification_jobs_nonnegative_attempts"
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            ondelete="RESTRICT",
            name="fk_shipment_notification_jobs_order_id_orders",
        ),
        sa.ForeignKeyConstraint(
            ["shipment_id"],
            ["shipments.id"],
            ondelete="RESTRICT",
            name="fk_shipment_notification_jobs_shipment_id_shipments",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_shipment_notification_jobs"),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_shipment_notification_jobs_idempotency_key"
        ),
    )
    op.create_index(
        "ix_shipment_notification_jobs_pending",
        "shipment_notification_jobs",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_shipment_notification_jobs_pending", table_name="shipment_notification_jobs")
    op.drop_table("shipment_notification_jobs")
    op.drop_index("ix_shipment_history_shipment_changed", table_name="shipment_history")
    op.drop_table("shipment_history")
    op.drop_index("ix_shipments_shipped_at", table_name="shipments")
    op.drop_table("shipments")
    op.drop_constraint("ck_orders_valid_fulfillment_status", "orders", type_="check")
    for column in (
        "picked_up_by",
        "picked_up_at",
        "pickup_ready_by",
        "pickup_ready_at",
        "fulfillment_ready_at",
        "fulfillment_status",
    ):
        op.drop_column("orders", column)
