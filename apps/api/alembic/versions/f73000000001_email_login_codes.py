"""One-time e-mail login codes (guest access to purchases).

Revision ID: f73000000001
Revises: f72000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f73000000001"
down_revision: str | None = "f72000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_login_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_ip", sa.String(64), nullable=False),
        sa.CheckConstraint("attempts >= 0", name=op.f("ck_email_login_codes_nonnegative_attempts")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_login_codes")),
    )
    op.create_index(
        "ix_email_login_codes_email_created", "email_login_codes", ["email", "created_at"]
    )
    op.create_index(
        "ix_email_login_codes_ip_created", "email_login_codes", ["requested_ip", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("email_login_codes")
