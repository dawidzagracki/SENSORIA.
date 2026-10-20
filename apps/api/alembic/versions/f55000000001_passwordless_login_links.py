"""Short-lived one-time customer login links.

Revision ID: f55000000001
Revises: f54000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f55000000001"
down_revision: str | None = "f54000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "login_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("invalidated_at", sa.DateTime(timezone=True)),
        sa.Column("requested_ip", sa.String(64), nullable=False),
        sa.Column("return_to", sa.Text(), server_default="/konto/biblioteka", nullable=False),
        sa.Column("email_job_id", postgresql.UUID(as_uuid=True)),
        sa.CheckConstraint("expires_at > created_at", name="ck_login_links_positive_lifetime"),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], ondelete="CASCADE", name="fk_login_links_customer"
        ),
        sa.ForeignKeyConstraint(
            ["email_job_id"],
            ["auth_email_jobs.id"],
            ondelete="SET NULL",
            name="fk_login_links_email_job",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_login_links"),
        sa.UniqueConstraint("token_hash", name="uq_login_links_token_hash"),
        sa.UniqueConstraint("email_job_id", name="uq_login_links_email_job_id"),
    )
    op.create_index("ix_login_links_customer_created", "login_links", ["customer_id", "created_at"])
    op.create_index(
        "uq_login_links_one_active_per_customer",
        "login_links",
        ["customer_id"],
        unique=True,
        postgresql_where=sa.text("used_at IS NULL AND invalidated_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_login_links_one_active_per_customer", table_name="login_links")
    op.drop_index("ix_login_links_customer_created", table_name="login_links")
    op.drop_table("login_links")
