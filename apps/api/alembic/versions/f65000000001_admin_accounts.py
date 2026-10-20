"""Administrator accounts and sessions.

Revision ID: f65000000001
Revises: f64000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f65000000001"
down_revision: str | None = "f64000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("failed_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_users")),
        sa.UniqueConstraint("email", name=op.f("uq_admin_users_email")),
        sa.CheckConstraint("role IN ('owner', 'staff')", name=op.f("ck_admin_users_valid_role")),
        sa.CheckConstraint("email = lower(btrim(email))", name=op.f("ck_admin_users_normalized_email")),
        sa.CheckConstraint(
            "failed_attempts >= 0", name=op.f("ck_admin_users_nonnegative_failed_attempts")
        ),
    )
    op.create_table(
        "admin_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("admin_id", sa.Uuid(), nullable=False),
        sa.Column("secret_hash", sa.String(64), nullable=False),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_hash", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_sessions")),
        sa.ForeignKeyConstraint(
            ["admin_id"], ["admin_users.id"], name=op.f("fk_admin_sessions_admin_id_admin_users"), ondelete="CASCADE"
        ),
        sa.UniqueConstraint("secret_hash", name=op.f("uq_admin_sessions_secret_hash")),
    )
    op.create_index("ix_admin_sessions_user", "admin_sessions", ["admin_id"])


def downgrade() -> None:
    op.drop_table("admin_sessions")
    op.drop_table("admin_users")
