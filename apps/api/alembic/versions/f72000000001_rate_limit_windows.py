"""Shared rate limit counters.

Revision ID: f72000000001
Revises: f71000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f72000000001"
down_revision: str | None = "f71000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_windows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(40), nullable=False),
        sa.Column("subject_hash", sa.String(64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hits", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rate_limit_windows")),
    )
    op.create_index(
        "uq_rate_limit_windows_subject",
        "rate_limit_windows",
        ["scope", "subject_hash", "window_started_at"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("rate_limit_windows")
