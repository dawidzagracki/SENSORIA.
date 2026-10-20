"""Add issued vouchers, durable PDF jobs and private PDF metadata.

Revision ID: aa4500000001
Revises: c30_pickup_point_snapshots
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "aa4500000001"
down_revision: str | None = "c30_pickup_point_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("order_items", sa.Column("product_name_snapshot", sa.String(200)))
    op.add_column("order_items", sa.Column("voucher_snapshot", postgresql.JSONB()))

    op.create_table(
        "stored_files",
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("stored_name", sa.String(64), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_year", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, default=uuid4),
        sa.CheckConstraint("category IN ('vouchers')", name=op.f("ck_stored_files_valid_category")),
        sa.CheckConstraint("size_bytes > 0", name=op.f("ck_stored_files_positive_size")),
        sa.CheckConstraint("length(stored_name) = 64", name=op.f("ck_stored_files_valid_stored_name")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stored_files")),
        sa.UniqueConstraint("stored_name", name=op.f("uq_stored_files_stored_name")),
    )
    op.create_index("ix_stored_files_category_scope", "stored_files", ["category", "scope_id"])

    op.create_table(
        "vouchers",
        sa.Column("code", sa.String(13), nullable=False),
        sa.Column("order_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("unit_index", sa.Integer(), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("variant", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True)),
        sa.Column("redeemed_by", sa.String(200)),
        sa.Column("pdf_file_id", postgresql.UUID(as_uuid=True)),
        sa.Column("recipient_email", sa.String(320)),
        sa.Column("issue_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, default=uuid4),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("unit_index >= 0", name=op.f("ck_vouchers_nonnegative_unit_index")),
        sa.CheckConstraint("status IN ('active', 'redeemed', 'expired', 'cancelled')", name=op.f("ck_vouchers_valid_status")),
        sa.CheckConstraint("valid_until > issued_at", name=op.f("ck_vouchers_valid_validity")),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"], ondelete="RESTRICT", name=op.f("fk_vouchers_order_item_id_order_items")),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT", name=op.f("fk_vouchers_product_id_products")),
        sa.ForeignKeyConstraint(["pdf_file_id"], ["stored_files.id"], ondelete="SET NULL", name=op.f("fk_vouchers_pdf_file_id_stored_files")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vouchers")),
        sa.UniqueConstraint("code", name=op.f("uq_vouchers_code")),
        sa.UniqueConstraint("order_item_id", "unit_index", name=op.f("uq_vouchers_order_item_id")),
    )
    op.create_index("ix_vouchers_product_status_valid_until", "vouchers", ["product_id", "status", "valid_until"])

    op.create_table(
        "voucher_pdf_jobs",
        sa.Column("voucher_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, default=uuid4),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'processing', 'complete', 'failed')", name=op.f("ck_voucher_pdf_jobs_valid_status")),
        sa.CheckConstraint("attempts >= 0", name=op.f("ck_voucher_pdf_jobs_nonnegative_attempts")),
        sa.ForeignKeyConstraint(["voucher_id"], ["vouchers.id"], ondelete="CASCADE", name=op.f("fk_voucher_pdf_jobs_voucher_id_vouchers")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_voucher_pdf_jobs")),
        sa.UniqueConstraint("voucher_id", name=op.f("uq_voucher_pdf_jobs_voucher_id")),
    )
    op.create_index("ix_voucher_pdf_jobs_dispatch", "voucher_pdf_jobs", ["status", "available_at"])

    op.create_table(
        "voucher_verification_windows",
        sa.Column("subject_hash", sa.String(64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, default=uuid4),
        sa.CheckConstraint("request_count >= 0", name=op.f("ck_voucher_verification_windows_nonnegative_request_count")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_voucher_verification_windows")),
        sa.UniqueConstraint("subject_hash", "window_started_at", name=op.f("uq_voucher_verification_windows_subject_hash")),
    )
    op.create_index("ix_voucher_verification_windows_expiry", "voucher_verification_windows", ["window_started_at"])


def downgrade() -> None:
    op.drop_index("ix_voucher_verification_windows_expiry", table_name="voucher_verification_windows")
    op.drop_table("voucher_verification_windows")
    op.drop_index("ix_voucher_pdf_jobs_dispatch", table_name="voucher_pdf_jobs")
    op.drop_table("voucher_pdf_jobs")
    op.drop_index("ix_vouchers_product_status_valid_until", table_name="vouchers")
    op.drop_table("vouchers")
    op.drop_index("ix_stored_files_category_scope", table_name="stored_files")
    op.drop_table("stored_files")
    op.drop_column("order_items", "voucher_snapshot")
    op.drop_column("order_items", "product_name_snapshot")
