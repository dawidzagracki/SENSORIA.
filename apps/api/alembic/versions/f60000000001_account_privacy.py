"""Append-only consents and durable account privacy workflows.

Revision ID: f60000000001
Revises: f59000000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f60000000001"
down_revision: str | None = "f59000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("deleted_at", sa.DateTime(timezone=True)))
    op.create_table(
        "consent_text_versions",
        sa.Column("consent_type", sa.String(40), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_consent_text_versions")),
        sa.UniqueConstraint(
            "consent_type", "version", name=op.f("uq_consent_text_versions_consent_type")
        ),
    )
    op.create_table(
        "customer_consents",
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("subject_digest", sa.String(64), nullable=False),
        sa.Column("consent_type", sa.String(40), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("consent_text_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ip_hash", sa.String(64), nullable=True),
        sa.Column("order_consent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(
            "consent_type IN ('new_materials', 'voucher_reminders', 'review_requests', "
            "'checkout_terms', 'checkout_digital', 'checkout_marketing')",
            name=op.f("ck_customer_consents_valid_consent_type"),
        ),
        sa.CheckConstraint(
            "customer_id IS NOT NULL OR email IS NOT NULL OR subject_digest IS NOT NULL",
            name=op.f("ck_customer_consents_has_subject"),
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            ondelete="SET NULL",
            name=op.f("fk_customer_consents_customer_id_customers"),
        ),
        sa.ForeignKeyConstraint(
            ["consent_text_id"],
            ["consent_text_versions.id"],
            ondelete="RESTRICT",
            name=op.f("fk_customer_consents_consent_text_id_consent_text_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customer_consents")),
        sa.ForeignKeyConstraint(
            ["order_consent_id"],
            ["order_consents.id"],
            ondelete="SET NULL",
            name=op.f("fk_customer_consents_order_consent_id_order_consents"),
        ),
        sa.UniqueConstraint("order_consent_id", name=op.f("uq_customer_consents_order_consent_id")),
    )
    op.create_index(
        "ix_customer_consents_account_type_time",
        "customer_consents",
        ["customer_id", "consent_type", "occurred_at"],
    )
    op.create_index(
        "ix_customer_consents_email_type_time",
        "customer_consents",
        ["email", "consent_type", "occurred_at"],
    )
    op.create_table(
        "consent_guest_imports",
        sa.Column("order_consent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consent_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["consent_event_id"],
            ["customer_consents.id"],
            ondelete="RESTRICT",
            name=op.f("fk_consent_guest_imports_consent_event_id_customer_consents"),
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            ondelete="CASCADE",
            name=op.f("fk_consent_guest_imports_customer_id_customers"),
        ),
        sa.ForeignKeyConstraint(
            ["order_consent_id"],
            ["order_consents.id"],
            ondelete="RESTRICT",
            name=op.f("fk_consent_guest_imports_order_consent_id_order_consents"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_consent_guest_imports")),
        sa.UniqueConstraint(
            "order_consent_id", name=op.f("uq_consent_guest_imports_order_consent_id")
        ),
    )
    op.create_table(
        "account_privacy_jobs",
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), server_default="pending", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("file_name", sa.String(80), nullable=True),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('export', 'deletion')", name=op.f("ck_account_privacy_jobs_valid_kind")
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'ready', 'complete', 'failed', 'cancelled')",
            name=op.f("ck_account_privacy_jobs_valid_status"),
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            ondelete="RESTRICT",
            name=op.f("fk_account_privacy_jobs_customer_id_customers"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account_privacy_jobs")),
    )
    op.create_index(
        "ix_account_privacy_jobs_dispatch", "account_privacy_jobs", ["status", "created_at"]
    )
    op.create_index(
        "ix_account_privacy_jobs_customer_created",
        "account_privacy_jobs",
        ["customer_id", "created_at"],
    )
    op.create_table(
        "deleted_email_suppressions",
        sa.Column("email_digest", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deleted_email_suppressions")),
        sa.UniqueConstraint(
            "email_digest", name=op.f("uq_deleted_email_suppressions_email_digest")
        ),
    )
    texts = [
        (
            "new_materials",
            "v1",
            (
                "Wiadomości o nowych materiałach. Raz w miesiącu, bez natrętnych przypomnień. "
                "Wypiszesz się jednym kliknięciem."
            ),
        ),
        (
            "voucher_reminders",
            "v1",
            (
                "Przypomnienia o voucherach. Przypomnimy przed terminem zgodnie z aktualnymi "
                "progami skonfigurowanymi w sklepie."
            ),
        ),
        (
            "review_requests",
            "v1",
            "Prośby o opinię. Zapytamy o zdanie po zakupie. Możesz to wyłączyć.",
        ),
    ]
    identifiers = (
        "60000000-0000-4000-8000-000000000001",
        "60000000-0000-4000-8000-000000000002",
        "60000000-0000-4000-8000-000000000003",
    )
    for identifier, (consent_type, version, text) in zip(identifiers, texts, strict=True):
        op.execute(
            sa.text(
                "INSERT INTO consent_text_versions (id, consent_type, version, text) "
                "VALUES (CAST(:id AS uuid), :kind, :version, :text)"
            ).bindparams(id=identifier, kind=consent_type, version=version, text=text)
        )
    op.execute(
        """
        CREATE FUNCTION prevent_consent_text_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Consent text versions are immutable';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER trg_consent_text_versions_immutable "
        "BEFORE UPDATE OR DELETE ON consent_text_versions "
        "FOR EACH ROW EXECUTE FUNCTION prevent_consent_text_mutation()"
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_consent_text_versions_immutable ON consent_text_versions"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_consent_text_mutation()")
    op.drop_index("ix_account_privacy_jobs_customer_created", table_name="account_privacy_jobs")
    op.drop_index("ix_account_privacy_jobs_dispatch", table_name="account_privacy_jobs")
    op.drop_table("deleted_email_suppressions")
    op.drop_table("account_privacy_jobs")
    op.drop_table("consent_guest_imports")
    op.drop_index("ix_customer_consents_email_type_time", table_name="customer_consents")
    op.drop_index("ix_customer_consents_account_type_time", table_name="customer_consents")
    op.drop_table("customer_consents")
    op.drop_table("consent_text_versions")
    op.drop_column("customers", "deleted_at")
