"""Information pages.

Revision ID: f67000000001
Revises: f66000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f67000000001"
down_revision: str | None = "f66000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "content_pages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.String(300), nullable=True),
        sa.Column("blocks", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(10), server_default="draft", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_pages")),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["admin_users.id"], name=op.f("fk_content_pages_updated_by_admin_users"), ondelete="SET NULL"
        ),
        sa.UniqueConstraint("slug", name=op.f("uq_content_pages_slug")),
        sa.CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name=op.f("ck_content_pages_valid_slug")),
        sa.CheckConstraint("status IN ('draft', 'published')", name=op.f("ck_content_pages_valid_status")),
        sa.CheckConstraint("length(btrim(title)) > 0", name=op.f("ck_content_pages_nonempty_title")),
    )


def downgrade() -> None:
    op.drop_table("content_pages")
