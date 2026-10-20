"""Add an append-only stock ledger and shipping snapshots.

Revision ID: f51000000001
Revises: f50000000001
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f51000000001"
down_revision: str | None = "f50000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "product_book",
        sa.Column("low_stock_threshold", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_check_constraint(
        "ck_product_book_nonnegative_low_stock_threshold",
        "product_book",
        "low_stock_threshold >= 0",
    )
    op.add_column(
        "stock_reservations",
        sa.Column("order_item_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_stock_reservations_order_item_id_order_items",
        "stock_reservations",
        "order_items",
        ["order_item_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(
        "UPDATE stock_reservations AS reservation SET order_item_id = ("
        "SELECT item.id FROM order_items AS item "
        "WHERE item.order_id = reservation.order_id "
        "AND item.product_id = reservation.product_id ORDER BY item.id LIMIT 1)"
    )
    op.add_column("order_items", sa.Column("shipping_snapshot", postgresql.JSONB(), nullable=True))

    op.create_table(
        "stock_movements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("change", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=24), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("order_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_reference", sa.String(length=100), nullable=True),
        sa.Column("operation_key", sa.String(length=160), nullable=False),
        sa.Column("performed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint("change <> 0", name="ck_stock_movements_nonzero_change"),
        sa.CheckConstraint(
            "reason IN ('purchase', 'return', 'manual_adjustment', 'correction')",
            name="ck_stock_movements_valid_reason",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], ondelete="RESTRICT", name="fk_stock_movements_product_id_products"
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], ondelete="RESTRICT", name="fk_stock_movements_order_id_orders"
        ),
        sa.ForeignKeyConstraint(
            ["order_item_id"], ["order_items.id"], ondelete="RESTRICT", name="fk_stock_movements_order_item_id_order_items"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_stock_movements"),
        sa.UniqueConstraint("operation_key", name="uq_stock_movements_operation_key"),
    )
    op.create_index(
        "ix_stock_movements_product_created", "stock_movements", ["product_id", "created_at"]
    )

    op.create_table(
        "low_stock_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("movement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("previous_stock", sa.Integer(), nullable=False),
        sa.Column("current_stock", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'queued', 'sent', 'failed')",
            name="ck_low_stock_alerts_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], ondelete="RESTRICT", name="fk_low_stock_alerts_product_id_products"
        ),
        sa.ForeignKeyConstraint(
            ["movement_id"], ["stock_movements.id"], ondelete="RESTRICT", name="fk_low_stock_alerts_movement_id_stock_movements"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_low_stock_alerts"),
        sa.UniqueConstraint("movement_id", name="uq_low_stock_alerts_movement_id"),
    )

    op.create_table(
        "stock_fulfillment_conflicts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_quantity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="open", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("requested_quantity > 0", name="ck_stock_fulfillment_conflicts_positive_requested_quantity"),
        sa.CheckConstraint("status IN ('open', 'resolved')", name="ck_stock_fulfillment_conflicts_valid_status"),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], ondelete="RESTRICT", name="fk_stock_fulfillment_conflicts_order_id_orders"
        ),
        sa.ForeignKeyConstraint(
            ["order_item_id"], ["order_items.id"], ondelete="RESTRICT", name="fk_stock_fulfillment_conflicts_order_item_id_order_items"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], ondelete="RESTRICT", name="fk_stock_fulfillment_conflicts_product_id_products"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_stock_fulfillment_conflicts"),
        sa.UniqueConstraint("order_item_id", name="uq_stock_fulfillment_conflicts_order_item_id"),
    )

    # Existing stock has no movement history. Preserve its current value as one opening correction.
    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT product_id, stock_quantity FROM product_book WHERE stock_quantity > 0")
    ).all()
    for product_id, stock_quantity in rows:
        movement_id = uuid4()
        connection.execute(
            sa.text(
                "INSERT INTO stock_movements "
                "(id, product_id, change, reason, operation_key, note) "
                "VALUES (:id, :product_id, :change, 'correction', :key, :note)"
            ),
            {
                "id": movement_id,
                "product_id": product_id,
                "change": stock_quantity,
                "key": f"opening:{product_id}",
                "note": "Stan otwarcia przeniesiony z product_book podczas migracji f51000000001.",
            },
        )
        connection.execute(
            sa.text(
                "INSERT INTO audit_log "
                "(id, actor_type, actor_id, entity_type, entity_id, action, payload) "
                "VALUES (:id, 'system', NULL, 'stock_movement', :entity_id, "
                "'stock.opening.migrated', CAST(:payload AS jsonb))"
            ),
            {
                "id": uuid4(),
                "entity_id": movement_id,
                "payload": (
                    '{"product_id":"'
                    + str(product_id)
                    + '","change":'
                    + str(stock_quantity)
                    + ',"reason":"correction","source":"f51000000001"}'
                ),
            },
        )

    op.execute(
        """
        CREATE FUNCTION sensoria_guard_stock_quantity() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.stock_quantity <> 0 THEN
                    RAISE EXCEPTION 'initial stock must be recorded as a stock movement';
                END IF;
                RETURN NEW;
            END IF;
            IF NEW.stock_quantity IS DISTINCT FROM OLD.stock_quantity
               AND current_setting('sensoria.stock_movement_write', true) IS DISTINCT FROM 'on' THEN
                RAISE EXCEPTION 'stock_quantity can only be updated by stock_movements';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_product_book_stock_insert_guard
        BEFORE INSERT ON product_book
        FOR EACH ROW EXECUTE FUNCTION sensoria_guard_stock_quantity();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_product_book_stock_guard
        BEFORE UPDATE OF stock_quantity ON product_book
        FOR EACH ROW EXECUTE FUNCTION sensoria_guard_stock_quantity();
        """
    )
    op.execute(
        """
        CREATE FUNCTION sensoria_apply_stock_movement() RETURNS trigger AS $$
        DECLARE
            old_quantity integer;
            new_quantity integer;
            reserved integer;
        BEGIN
            SELECT stock_quantity
              INTO old_quantity
              FROM product_book WHERE product_id = NEW.product_id FOR UPDATE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'Product book details do not exist';
            END IF;
            new_quantity := old_quantity + NEW.change;
            IF new_quantity < 0 THEN
                RAISE EXCEPTION 'Stock cannot become negative';
            END IF;
            SELECT COALESCE(SUM(sr.quantity), 0)::integer INTO reserved
              FROM stock_reservations sr JOIN orders o ON o.id = sr.order_id
             WHERE sr.product_id = NEW.product_id
               AND sr.released_at IS NULL AND sr.expires_at > now()
               AND o.status = 'pending_payment';
            IF new_quantity < reserved THEN
                RAISE EXCEPTION 'Stock cannot fall below active reservations';
            END IF;
            PERFORM set_config('sensoria.stock_movement_write', 'on', true);
            UPDATE product_book SET stock_quantity = new_quantity
             WHERE product_id = NEW.product_id;
            PERFORM set_config('sensoria.stock_movement_write', 'off', true);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_stock_movements_apply
        AFTER INSERT ON stock_movements
        FOR EACH ROW EXECUTE FUNCTION sensoria_apply_stock_movement();
        """
    )
    op.execute(
        """
        CREATE FUNCTION sensoria_immutable_stock_movement() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'stock movements are append only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_stock_movements_immutable
        BEFORE UPDATE OR DELETE ON stock_movements
        FOR EACH ROW EXECUTE FUNCTION sensoria_immutable_stock_movement();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_stock_movements_immutable ON stock_movements"
    )
    op.execute("DROP FUNCTION IF EXISTS sensoria_immutable_stock_movement()")
    op.execute("DROP TRIGGER IF EXISTS trg_stock_movements_apply ON stock_movements")
    op.execute("DROP FUNCTION IF EXISTS sensoria_apply_stock_movement()")
    op.execute("DROP TRIGGER IF EXISTS trg_product_book_stock_guard ON product_book")
    op.execute("DROP TRIGGER IF EXISTS trg_product_book_stock_insert_guard ON product_book")
    op.execute("DROP FUNCTION IF EXISTS sensoria_guard_stock_quantity()")
    op.drop_table("stock_fulfillment_conflicts")
    op.drop_table("low_stock_alerts")
    op.drop_index("ix_stock_movements_product_created", table_name="stock_movements")
    op.drop_table("stock_movements")
    op.drop_column("order_items", "shipping_snapshot")
    op.drop_constraint(
        "fk_stock_reservations_order_item_id_order_items", "stock_reservations", type_="foreignkey"
    )
    op.drop_column("stock_reservations", "order_item_id")
    op.drop_constraint(
        "ck_product_book_nonnegative_low_stock_threshold", "product_book", type_="check"
    )
    op.drop_column("product_book", "low_stock_threshold")
