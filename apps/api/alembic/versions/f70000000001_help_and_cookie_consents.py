"""FAQ entries and cookie consent register.

Revision ID: f70000000001
Revises: f69000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f70000000001"
down_revision: str | None = "f69000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "faq_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("question", sa.String(300), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("published", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_faq_entries")),
        sa.CheckConstraint("length(btrim(question)) > 0", name=op.f("ck_faq_entries_nonempty_question")),
        sa.CheckConstraint("length(btrim(answer)) > 0", name=op.f("ck_faq_entries_nonempty_answer")),
    )
    op.create_table(
        "cookie_consents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("policy_version", sa.String(20), nullable=False),
        sa.Column("analytics", sa.Boolean(), nullable=False),
        sa.Column("marketing", sa.Boolean(), nullable=False),
        sa.Column("ip_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cookie_consents")),
    )
    op.create_index("ix_cookie_consents_subject_created", "cookie_consents", ["subject_id", "created_at"])


def downgrade() -> None:
    op.drop_table("cookie_consents")
    op.drop_table("faq_entries")
