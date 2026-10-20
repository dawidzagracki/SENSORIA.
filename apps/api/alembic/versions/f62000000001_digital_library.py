"""Digital library: product files, entitlements, download links, progress.

Revision ID: f62000000001
Revises: f61000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f62000000001"
down_revision: str | None = "f61000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = sa.func.now()


def _ts(name: str, *, nullable: bool = False, default: bool = True) -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        nullable=nullable,
        server_default=NOW if default else None,
    )


def upgrade() -> None:
    op.drop_constraint(op.f("ck_stored_files_valid_category"), "stored_files", type_="check")
    op.create_check_constraint(
        op.f("ck_stored_files_valid_category"),
        "stored_files",
        "category IN ('vouchers', 'products', 'watermarked')",
    )
    op.create_table(
        "product_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("stored_file_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("chapter_id", sa.Uuid(), nullable=True),
        _ts("created_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_files")),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name=op.f("fk_product_files_product_id_products"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["stored_file_id"],
            ["stored_files.id"],
            name=op.f("fk_product_files_stored_file_id_stored_files"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id"],
            ["product_audiobook_chapters.id"],
            name=op.f("fk_product_files_chapter_id_product_audiobook_chapters"),
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("stored_file_id", name=op.f("uq_product_files_stored_file_id")),
        sa.CheckConstraint("kind IN ('pdf', 'audio')", name=op.f("ck_product_files_valid_kind")),
        sa.CheckConstraint("position >= 0", name=op.f("ck_product_files_nonnegative_position")),
    )
    op.create_index("ix_product_files_product_position", "product_files", ["product_id", "position"])
    op.create_table(
        "ebook_chapters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("blocks", postgresql.JSONB(), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ebook_chapters")),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name=op.f("fk_ebook_chapters_product_id_products"), ondelete="CASCADE"
        ),
        sa.UniqueConstraint("product_id", "position", name=op.f("uq_ebook_chapters_product_id")),
        sa.CheckConstraint("position >= 0", name=op.f("ck_ebook_chapters_nonnegative_position")),
        sa.CheckConstraint("length(btrim(title)) > 0", name=op.f("ck_ebook_chapters_nonempty_title")),
        sa.CheckConstraint(
            "page_count IS NULL OR page_count > 0", name=op.f("ck_ebook_chapters_positive_page_count")
        ),
    )
    op.create_table(
        "entitlements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("order_item_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("status", sa.String(10), server_default="active", nullable=False),
        _ts("granted_at"),
        _ts("revoked_at", nullable=True, default=False),
        sa.Column("revoked_reason", sa.Text(), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_entitlements")),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name=op.f("fk_entitlements_order_id_orders"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["order_item_id"],
            ["order_items.id"],
            name=op.f("fk_entitlements_order_item_id_order_items"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name=op.f("fk_entitlements_product_id_products"), ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("order_item_id", name=op.f("uq_entitlements_order_item_id")),
        sa.CheckConstraint("status IN ('active', 'revoked')", name=op.f("ck_entitlements_valid_status")),
        sa.CheckConstraint("kind IN ('digital', 'audiobook')", name=op.f("ck_entitlements_valid_kind")),
    )
    op.create_index("ix_entitlements_order", "entitlements", ["order_id"])
    op.create_index("ix_entitlements_product", "entitlements", ["product_id"])
    op.create_table(
        "download_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("entitlement_id", sa.Uuid(), nullable=False),
        sa.Column("product_file_id", sa.Uuid(), nullable=False),
        _ts("expires_at", default=False),
        sa.Column("max_uses", sa.Integer(), nullable=False),
        sa.Column("use_count", sa.Integer(), server_default="0", nullable=False),
        _ts("revoked_at", nullable=True, default=False),
        _ts("created_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_download_links")),
        sa.ForeignKeyConstraint(
            ["entitlement_id"],
            ["entitlements.id"],
            name=op.f("fk_download_links_entitlement_id_entitlements"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_file_id"],
            ["product_files.id"],
            name=op.f("fk_download_links_product_file_id_product_files"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("token_hash", name=op.f("uq_download_links_token_hash")),
        sa.CheckConstraint("max_uses > 0", name=op.f("ck_download_links_positive_max_uses")),
        sa.CheckConstraint("use_count >= 0", name=op.f("ck_download_links_nonnegative_use_count")),
    )
    op.create_index(
        "ix_download_links_entitlement_file", "download_links", ["entitlement_id", "product_file_id"]
    )
    op.create_table(
        "watermarked_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entitlement_id", sa.Uuid(), nullable=False),
        sa.Column("product_file_id", sa.Uuid(), nullable=False),
        sa.Column("stored_file_id", sa.Uuid(), nullable=False),
        _ts("created_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_watermarked_files")),
        sa.ForeignKeyConstraint(
            ["entitlement_id"],
            ["entitlements.id"],
            name=op.f("fk_watermarked_files_entitlement_id_entitlements"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_file_id"],
            ["product_files.id"],
            name=op.f("fk_watermarked_files_product_file_id_product_files"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["stored_file_id"],
            ["stored_files.id"],
            name=op.f("fk_watermarked_files_stored_file_id_stored_files"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "entitlement_id", "product_file_id", name=op.f("uq_watermarked_files_entitlement_id")
        ),
    )
    op.create_table(
        "content_progress",
        sa.Column("entitlement_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("offset_seconds", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completed", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("font_scale", sa.Integer(), server_default="100", nullable=False),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("entitlement_id", name=op.f("pk_content_progress")),
        sa.ForeignKeyConstraint(
            ["entitlement_id"],
            ["entitlements.id"],
            name=op.f("fk_content_progress_entitlement_id_entitlements"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("position >= 0", name=op.f("ck_content_progress_nonnegative_position")),
        sa.CheckConstraint("offset_seconds >= 0", name=op.f("ck_content_progress_nonnegative_offset")),
    )


def downgrade() -> None:
    for table in (
        "content_progress",
        "watermarked_files",
        "download_links",
        "entitlements",
        "ebook_chapters",
        "product_files",
    ):
        op.drop_table(table)
    op.drop_constraint(op.f("ck_stored_files_valid_category"), "stored_files", type_="check")
    op.create_check_constraint(
        op.f("ck_stored_files_valid_category"), "stored_files", "category IN ('vouchers')"
    )
