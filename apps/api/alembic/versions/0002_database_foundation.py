"""Create shared application settings and audit event tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_database_foundation"
down_revision: str | None = "0001_initial_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create shared tables and install pgcrypto without using it for UUIDs."""

    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("length(btrim(key)) > 0", name="nonempty_key"),
        sa.PrimaryKeyConstraint("id", name="pk_app_settings"),
        sa.UniqueConstraint("key", name="uq_app_settings_key"),
    )
    op.create_table(
        "audit_log",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "actor_type IN ('customer', 'administrator', 'system')",
            name="valid_actor_type",
        ),
        sa.CheckConstraint("length(btrim(entity_type)) > 0", name="nonempty_entity_type"),
        sa.CheckConstraint("length(btrim(action)) > 0", name="nonempty_action"),
        sa.PrimaryKeyConstraint("id", name="pk_audit_log"),
    )
    op.create_index(
        "ix_audit_log_actor_created_at",
        "audit_log",
        ["actor_type", "actor_id", "created_at"],
    )
    op.create_index(
        "ix_audit_log_entity_created_at",
        "audit_log",
        ["entity_type", "entity_id", "created_at"],
    )
    op.create_index("ix_audit_log_action_created_at", "audit_log", ["action", "created_at"])
    op.create_index(
        "ix_audit_log_payload",
        "audit_log",
        ["payload"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    """Drop only this revision's tables; retain shared pgcrypto extension."""

    op.drop_table("audit_log")
    op.drop_table("app_settings")
