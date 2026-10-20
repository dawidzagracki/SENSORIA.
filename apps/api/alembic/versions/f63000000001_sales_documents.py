"""Sales documents with gapless numbering; documents file category.

Revision ID: f63000000001
Revises: f62000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f63000000001"
down_revision: str | None = "f62000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_stored_files_valid_category"), "stored_files", type_="check")
    op.create_check_constraint(
        op.f("ck_stored_files_valid_category"),
        "stored_files",
        "category IN ('vouchers', 'products', 'watermarked', 'documents')",
    )
    op.create_table(
        "document_counters",
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last_number", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("kind", "year", name=op.f("pk_document_counters")),
        sa.CheckConstraint(
            "last_number >= 0", name=op.f("ck_document_counters_nonnegative_last_number")
        ),
    )
    op.create_table(
        "sales_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column("stored_file_id", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sales_documents")),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name=op.f("fk_sales_documents_order_id_orders"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["stored_file_id"],
            ["stored_files.id"],
            name=op.f("fk_sales_documents_stored_file_id_stored_files"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("order_id", "kind", name=op.f("uq_sales_documents_order_id")),
        sa.UniqueConstraint("number", name=op.f("uq_sales_documents_number")),
        sa.CheckConstraint("kind IN ('receipt', 'invoice')", name=op.f("ck_sales_documents_valid_kind")),
    )


def downgrade() -> None:
    op.drop_table("sales_documents")
    op.drop_table("document_counters")
    op.drop_constraint(op.f("ck_stored_files_valid_category"), "stored_files", type_="check")
    op.create_check_constraint(
        op.f("ck_stored_files_valid_category"),
        "stored_files",
        "category IN ('vouchers', 'products', 'watermarked')",
    )
