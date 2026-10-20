"""Track product gross-price versions and audit changes.

Revision ID: f31a9d4b
Revises: 08f9476a46d2
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "f31a9d4b"
down_revision: str | None = "08f9476a46d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BACKFILL_REASON = "Początkowy snapshot przy uruchomieniu historii cen"


def upgrade() -> None:
    connection = op.get_bind()
    invalid_count = connection.scalar(
        sa.text(
            "SELECT count(*) FROM products "
            "WHERE compare_at_price IS NOT NULL "
            "AND (price IS NULL OR compare_at_price <= price)"
        )
    )
    if invalid_count:
        raise RuntimeError(
            "Migracja przerwana: istnieją produkty z nieprawidłową ceną porównawczą. "
            "Popraw je jawnie przed ponownym uruchomieniem migracji."
        )

    op.create_check_constraint(
        "compare_at_price_above_price",
        "products",
        "compare_at_price IS NULL OR (price IS NOT NULL AND compare_at_price > price)",
    )
    op.create_table(
        "price_history",
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("price", sa.BigInteger(), nullable=True),
        sa.Column("compare_at_price", sa.BigInteger(), nullable=True),
        sa.Column("vat_rate", sa.String(length=16), nullable=True),
        sa.Column(
            "valid_from",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("changed_by", sa.Uuid(), nullable=True),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("price IS NULL OR price >= 0", name="nonnegative_price"),
        sa.CheckConstraint(
            "compare_at_price IS NULL OR (price IS NOT NULL AND compare_at_price > price)",
            name="compare_above_price",
        ),
        sa.CheckConstraint(
            "vat_rate IS NULL OR vat_rate IN ('RATE_23', 'RATE_8', 'RATE_5', 'RATE_0', 'EXEMPT')",
            name="valid_vat_rate",
        ),
        sa.CheckConstraint(
            "actor_type IN ('customer', 'administrator', 'system')",
            name="valid_actor_type",
        ),
        sa.CheckConstraint("length(btrim(reason)) > 0", name="nonempty_reason"),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_price_history_product_id_products",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_price_history"),
        sa.UniqueConstraint("version", name="uq_price_history_version"),
    )
    op.create_index(
        "ix_price_history_product_valid_from",
        "price_history",
        ["product_id", "valid_from", "version"],
    )
    op.create_index("ix_price_history_product_version", "price_history", ["product_id", "version"])

    products = connection.execute(
        sa.text("SELECT id, price, compare_at_price, vat_rate FROM products")
    ).mappings()
    now = connection.scalar(sa.text("SELECT now()"))
    history_rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []
    for product in products:
        current = {
            "price": product["price"],
            "compare_at_price": product["compare_at_price"],
            "vat_rate": product["vat_rate"],
        }
        history_rows.append(
            {
                "id": uuid4(),
                "product_id": product["id"],
                **current,
                "valid_from": now,
                "changed_by": None,
                "actor_type": "system",
                "reason": _BACKFILL_REASON,
            }
        )
        audit_rows.append(
            {
                "id": uuid4(),
                "created_at": now,
                "actor_type": "system",
                "actor_id": None,
                "entity_type": "product",
                "entity_id": product["id"],
                "action": "product.price.history_started",
                "payload": {
                    "reason": _BACKFILL_REASON,
                    "previous": None,
                    "current": current,
                },
            }
        )
    if history_rows:
        op.bulk_insert(
            sa.table(
                "price_history",
                sa.column("id", sa.Uuid()),
                sa.column("product_id", sa.Uuid()),
                sa.column("price", sa.BigInteger()),
                sa.column("compare_at_price", sa.BigInteger()),
                sa.column("vat_rate", sa.String(16)),
                sa.column("valid_from", sa.DateTime(timezone=True)),
                sa.column("changed_by", sa.Uuid()),
                sa.column("actor_type", sa.String(20)),
                sa.column("reason", sa.String(500)),
            ),
            history_rows,
        )
        op.bulk_insert(
            sa.table(
                "audit_log",
                sa.column("id", sa.Uuid()),
                sa.column("created_at", sa.DateTime(timezone=True)),
                sa.column("actor_type", sa.String(20)),
                sa.column("actor_id", sa.Uuid()),
                sa.column("entity_type", sa.String(100)),
                sa.column("entity_id", sa.Uuid()),
                sa.column("action", sa.String(100)),
                sa.column("payload", JSONB),
            ),
            audit_rows,
        )

    op.execute(
        sa.text(
            """
        CREATE FUNCTION sensoria_guard_product_price_write() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF current_setting('sensoria.price_write_guard', true) IS DISTINCT FROM 'on' THEN
                RAISE EXCEPTION 'Zmiany cen produktu muszą przejść przez ścieżkę ORM.'
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
        )
    )
    op.execute(
        sa.text(
            """
        CREATE TRIGGER trg_products_price_write_guard
        BEFORE INSERT OR UPDATE OF price, compare_at_price, vat_rate ON products
        FOR EACH ROW EXECUTE FUNCTION sensoria_guard_product_price_write();
        """
        )
    )
    op.execute(
        sa.text(
            """
        CREATE FUNCTION sensoria_reject_price_history_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Historia cen jest dopisywana i nie może być zmieniana ani usuwana.'
                USING ERRCODE = '42501';
        END;
        $$;
        """
        )
    )
    op.execute(
        sa.text(
            """
        CREATE TRIGGER trg_price_history_append_only
        BEFORE UPDATE OR DELETE ON price_history
        FOR EACH ROW EXECUTE FUNCTION sensoria_reject_price_history_mutation();
        """
        )
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_price_history_append_only ON price_history")
    op.execute("DROP TRIGGER IF EXISTS trg_products_price_write_guard ON products")
    op.execute("DROP FUNCTION IF EXISTS sensoria_reject_price_history_mutation()")
    op.execute("DROP FUNCTION IF EXISTS sensoria_guard_product_price_write()")
    op.drop_index("ix_price_history_product_version", table_name="price_history")
    op.drop_index("ix_price_history_product_valid_from", table_name="price_history")
    op.drop_table("price_history")
    op.drop_constraint("compare_at_price_above_price", "products", type_="check")
