"""Store independent, public PDF and audio sample metadata and access limits.

Revision ID: f021_product_samples
Revises: e920_product_media
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f021_product_samples"
down_revision: str | None = "e920_product_media"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("sample_open_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_check_constraint(
        "nonnegative_sample_open_count", "products", "sample_open_count >= 0"
    )

    op.add_column("product_digital", sa.Column("sample_file_path", sa.String(80), nullable=True))
    op.add_column("product_digital", sa.Column("sample_pages", sa.Integer(), nullable=True))
    op.add_column(
        "product_digital",
        sa.Column("sample_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_check_constraint(
        "positive_pdf_sample_pages",
        "product_digital",
        "sample_pages IS NULL OR sample_pages > 0",
    )
    op.create_check_constraint(
        "nonempty_pdf_sample_key",
        "product_digital",
        "sample_file_path IS NULL OR length(btrim(sample_file_path)) > 0",
    )
    op.create_check_constraint(
        "valid_pdf_sample_key",
        "product_digital",
        "sample_file_path IS NULL OR sample_file_path ~ "
        "'^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}\\.pdf$'",
    )
    op.create_check_constraint(
        "enabled_pdf_sample_complete",
        "product_digital",
        "NOT sample_enabled OR (sample_file_path IS NOT NULL AND sample_pages IS NOT NULL)",
    )

    op.add_column("product_audiobook", sa.Column("sample_file_path", sa.String(80), nullable=True))
    op.add_column(
        "product_audiobook", sa.Column("sample_duration_seconds", sa.Integer(), nullable=True)
    )
    op.add_column(
        "product_audiobook",
        sa.Column("sample_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_check_constraint(
        "positive_audio_sample_duration",
        "product_audiobook",
        "sample_duration_seconds IS NULL OR sample_duration_seconds > 0",
    )
    op.create_check_constraint(
        "nonempty_audio_sample_key",
        "product_audiobook",
        "sample_file_path IS NULL OR length(btrim(sample_file_path)) > 0",
    )
    op.create_check_constraint(
        "valid_audio_sample_key",
        "product_audiobook",
        "sample_file_path IS NULL OR sample_file_path ~ "
        "'^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}\\.mp3$'",
    )
    op.create_check_constraint(
        "enabled_audio_sample_complete",
        "product_audiobook",
        "NOT sample_enabled OR (sample_file_path IS NOT NULL "
        "AND sample_duration_seconds IS NOT NULL)",
    )

    op.create_table(
        "sample_rate_windows",
        sa.Column("client_key", sa.String(length=64), nullable=False),
        sa.Column(
            "window_started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("request_count", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("client_key", name=op.f("pk_sample_rate_windows")),
        sa.CheckConstraint(
            "request_count >= 0", name=op.f("ck_sample_rate_windows_nonnegative_request_count")
        ),
    )
    op.create_table(
        "sample_access_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("request_key", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sample_access_sessions")),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_sample_access_sessions_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sample_access_sessions_token_hash")),
        sa.UniqueConstraint("request_key", name=op.f("uq_sample_access_sessions_request_key")),
        sa.CheckConstraint(
            "request_count >= 0", name=op.f("ck_sample_access_sessions_nonnegative_request_count")
        ),
    )
    op.create_index(
        "ix_sample_access_sessions_expiry", "sample_access_sessions", ["expires_at"], unique=False
    )
    op.create_index(
        "ix_sample_access_sessions_product", "sample_access_sessions", ["product_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_sample_access_sessions_product", table_name="sample_access_sessions")
    op.drop_index("ix_sample_access_sessions_expiry", table_name="sample_access_sessions")
    op.drop_table("sample_access_sessions")
    op.drop_table("sample_rate_windows")

    op.drop_constraint("enabled_audio_sample_complete", "product_audiobook", type_="check")
    op.drop_constraint("valid_audio_sample_key", "product_audiobook", type_="check")
    op.drop_constraint("nonempty_audio_sample_key", "product_audiobook", type_="check")
    op.drop_constraint("positive_audio_sample_duration", "product_audiobook", type_="check")
    op.drop_column("product_audiobook", "sample_enabled")
    op.drop_column("product_audiobook", "sample_duration_seconds")
    op.drop_column("product_audiobook", "sample_file_path")

    op.drop_constraint("enabled_pdf_sample_complete", "product_digital", type_="check")
    op.drop_constraint("valid_pdf_sample_key", "product_digital", type_="check")
    op.drop_constraint("nonempty_pdf_sample_key", "product_digital", type_="check")
    op.drop_constraint("positive_pdf_sample_pages", "product_digital", type_="check")
    op.drop_column("product_digital", "sample_enabled")
    op.drop_column("product_digital", "sample_pages")
    op.drop_column("product_digital", "sample_file_path")

    op.drop_constraint("nonnegative_sample_open_count", "products", type_="check")
    op.drop_column("products", "sample_open_count")
