"""Add Polish full-text search, database refresh triggers, and query history.

Revision ID: b16f0a9c7d31
Revises: a15c0f3d2e71
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TSVECTOR

revision: str = "b16f0a9c7d31"
down_revision: str | None = "a15c0f3d2e71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Install search dictionaries and keep weighted vectors current in PostgreSQL."""

    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        """CREATE TEXT SEARCH DICTIONARY sensoria_polish_ispell (
            TEMPLATE = ispell,
            DictFile = sensoria_pl,
            AffFile = sensoria_pl
        )"""
    )
    op.execute(
        """CREATE TEXT SEARCH DICTIONARY sensoria_polish_unaccented_ispell (
            TEMPLATE = ispell,
            DictFile = sensoria_pl_folded,
            AffFile = sensoria_pl_folded
        )"""
    )
    op.execute(
        "CREATE TEXT SEARCH CONFIGURATION sensoria_polish (COPY = pg_catalog.simple)"
    )
    op.execute(
        """ALTER TEXT SEARCH CONFIGURATION sensoria_polish
           ALTER MAPPING FOR asciiword, word, hword, hword_part
           WITH sensoria_polish_ispell, pg_catalog.simple"""
    )
    op.execute(
        "CREATE TEXT SEARCH CONFIGURATION sensoria_polish_unaccented (COPY = pg_catalog.simple)"
    )
    op.execute(
        """ALTER TEXT SEARCH CONFIGURATION sensoria_polish_unaccented
           ALTER MAPPING FOR asciiword, word, hword, hword_part
           WITH public.unaccent, sensoria_polish_unaccented_ispell, pg_catalog.simple"""
    )

    op.add_column("products", sa.Column("search_vector", TSVECTOR(), nullable=True))
    op.add_column("products", sa.Column("search_vector_unaccented", TSVECTOR(), nullable=True))
    op.create_index("ix_products_search_vector_gin", "products", ["search_vector"], postgresql_using="gin")
    op.create_index(
        "ix_products_search_vector_unaccented_gin",
        "products",
        ["search_vector_unaccented"],
        postgresql_using="gin",
    )

    op.execute(
        r"""CREATE FUNCTION sensoria_search_clean_text(value text)
        RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
            SELECT regexp_replace(
                regexp_replace(coalesce(value, ''), '<[^>]*>', ' ', 'g'),
                '&[^[:space:];]+;', ' ', 'g'
            )
        $$"""
    )
    op.execute(
        """CREATE FUNCTION sensoria_set_product_search_vectors()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE category_text text;
        BEGIN
            SELECT string_agg(c.name, ' ' ORDER BY c.name)
              INTO category_text
              FROM product_categories pc
              JOIN categories c ON c.id = pc.category_id
             WHERE pc.product_id = NEW.id;

            NEW.search_vector :=
                setweight(to_tsvector('public.sensoria_polish'::regconfig,
                    sensoria_search_clean_text(NEW.name)), 'A') ||
                setweight(to_tsvector('public.sensoria_polish'::regconfig,
                    sensoria_search_clean_text(NEW.short_description)), 'B') ||
                setweight(to_tsvector('public.sensoria_polish'::regconfig,
                    sensoria_search_clean_text(category_text)), 'B') ||
                setweight(to_tsvector('public.sensoria_polish'::regconfig,
                    sensoria_search_clean_text(NEW.description)), 'C');

            NEW.search_vector_unaccented :=
                setweight(to_tsvector('public.sensoria_polish_unaccented'::regconfig,
                    sensoria_search_clean_text(NEW.name)), 'A') ||
                setweight(to_tsvector('public.sensoria_polish_unaccented'::regconfig,
                    sensoria_search_clean_text(NEW.short_description)), 'B') ||
                setweight(to_tsvector('public.sensoria_polish_unaccented'::regconfig,
                    sensoria_search_clean_text(category_text)), 'B') ||
                setweight(to_tsvector('public.sensoria_polish_unaccented'::regconfig,
                    sensoria_search_clean_text(NEW.description)), 'C');
            RETURN NEW;
        END
        $$"""
    )
    op.execute(
        """CREATE TRIGGER trg_products_search_vector
        BEFORE INSERT OR UPDATE OF name, short_description, description
        ON products FOR EACH ROW EXECUTE FUNCTION sensoria_set_product_search_vectors()"""
    )
    op.execute(
        """CREATE FUNCTION sensoria_refresh_product_search_vector(product_uuid uuid)
        RETURNS void LANGUAGE sql AS $$
            UPDATE products SET name = name WHERE id = product_uuid
        $$"""
    )
    op.execute(
        """CREATE FUNCTION sensoria_refresh_search_for_category_links()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                PERFORM sensoria_refresh_product_search_vector(NEW.product_id);
                RETURN NEW;
            ELSIF TG_OP = 'DELETE' THEN
                PERFORM sensoria_refresh_product_search_vector(OLD.product_id);
                RETURN OLD;
            ELSE
                PERFORM sensoria_refresh_product_search_vector(OLD.product_id);
                IF NEW.product_id <> OLD.product_id THEN
                    PERFORM sensoria_refresh_product_search_vector(NEW.product_id);
                END IF;
                RETURN NEW;
            END IF;
        END
        $$"""
    )
    op.execute(
        """CREATE TRIGGER trg_product_categories_search_vector
        AFTER INSERT OR UPDATE OR DELETE ON product_categories
        FOR EACH ROW EXECUTE FUNCTION sensoria_refresh_search_for_category_links()"""
    )
    op.execute(
        """CREATE FUNCTION sensoria_refresh_search_for_category_name()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE linked_product record;
        BEGIN
            FOR linked_product IN
                SELECT product_id FROM product_categories WHERE category_id = NEW.id
            LOOP
                PERFORM sensoria_refresh_product_search_vector(linked_product.product_id);
            END LOOP;
            RETURN NEW;
        END
        $$"""
    )
    op.execute(
        """CREATE TRIGGER trg_categories_search_vector
        AFTER UPDATE OF name ON categories
        FOR EACH ROW WHEN (OLD.name IS DISTINCT FROM NEW.name)
        EXECUTE FUNCTION sensoria_refresh_search_for_category_name()"""
    )

    # Existing content receives its vector using the same trigger as future writes.
    op.execute("UPDATE products SET name = name")
    op.alter_column("products", "search_vector", nullable=False)
    op.alter_column("products", "search_vector_unaccented", nullable=False)

    op.create_table(
        "search_queries",
        sa.Column("query_text", sa.String(length=160), nullable=False),
        sa.Column("normalized_query", sa.String(length=160), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("searched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("length(btrim(query_text)) > 0", name="ck_search_queries_nonempty_query"),
        sa.CheckConstraint("length(btrim(normalized_query)) > 0", name="ck_search_queries_nonempty_normalized_query"),
        sa.CheckConstraint("result_count >= 0", name="ck_search_queries_nonnegative_result_count"),
        sa.PrimaryKeyConstraint("id", name="pk_search_queries"),
    )
    op.create_index(
        "ix_search_queries_popularity",
        "search_queries",
        ["normalized_query", "searched_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove only this revision's objects; shared extensions remain installed."""

    op.drop_index("ix_search_queries_popularity", table_name="search_queries")
    op.drop_table("search_queries")
    op.execute("DROP TRIGGER trg_categories_search_vector ON categories")
    op.execute("DROP TRIGGER trg_product_categories_search_vector ON product_categories")
    op.execute("DROP TRIGGER trg_products_search_vector ON products")
    op.execute("DROP FUNCTION sensoria_refresh_search_for_category_name()")
    op.execute("DROP FUNCTION sensoria_refresh_search_for_category_links()")
    op.execute("DROP FUNCTION sensoria_refresh_product_search_vector(uuid)")
    op.execute("DROP FUNCTION sensoria_set_product_search_vectors()")
    op.execute("DROP FUNCTION sensoria_search_clean_text(text)")
    op.drop_index("ix_products_search_vector_unaccented_gin", table_name="products")
    op.drop_index("ix_products_search_vector_gin", table_name="products")
    op.drop_column("products", "search_vector_unaccented")
    op.drop_column("products", "search_vector")
    op.execute("DROP TEXT SEARCH CONFIGURATION sensoria_polish_unaccented")
    op.execute("DROP TEXT SEARCH CONFIGURATION sensoria_polish")
    op.execute("DROP TEXT SEARCH DICTIONARY sensoria_polish_unaccented_ispell")
    op.execute("DROP TEXT SEARCH DICTIONARY sensoria_polish_ispell")
