"""Initial Phase 2 tables: users, consents, intake_answers, audit_log.

Revision ID: phase2_initial
Revises:
Create Date: 2026-11-19

Append-only tables (consents, audit_log) get a Postgres trigger rejecting
UPDATE and DELETE. The trigger is Postgres-only; other dialects rely on the
application never issuing those statements.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "phase2_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REJECT_FUNCTION = """
CREATE OR REPLACE FUNCTION reject_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'append-only table: % updates and deletes are forbidden', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;
"""

_APPEND_ONLY_TABLES = ("consents", "audit_log")


def _is_postgres() -> bool:
    bind = op.get_bind()
    return bind is not None and bind.dialect.name == "postgresql"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("pseudonymous_handle", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("contact_encrypted", sa.Text, nullable=True),
        sa.Column("password_hash", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('user', 'navigator', 'clinician')", name="ck_users_role"),
        sa.CheckConstraint("language IN ('en', 'ar')", name="ck_users_language"),
    )
    op.create_table(
        "consents",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("granted", sa.Boolean, nullable=False),
        sa.Column("policy_version", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "scope IN ('intake', 'share_with_clinician', 'reminders', 'aggregate_analytics')",
            name="ck_consents_scope",
        ),
    )
    op.create_table(
        "intake_answers",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "user_id", sa.Uuid, sa.ForeignKey("users.id"), nullable=False, unique=True, index=True
        ),
        sa.Column("answers_encrypted", sa.Text, nullable=False),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("actor_id", sa.Uuid, sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("actor_role", sa.String(16), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("object_type", sa.String(64), nullable=False),
        sa.Column("object_id", sa.Uuid, nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("detail", sa.JSON, nullable=False),
    )
    if _is_postgres():
        op.execute(sa.text(_REJECT_FUNCTION))
        for table in _APPEND_ONLY_TABLES:
            op.execute(
                sa.text(
                    f"CREATE TRIGGER {table}_no_update_delete "
                    f"BEFORE UPDATE OR DELETE ON {table} "
                    "FOR EACH ROW EXECUTE FUNCTION reject_mutation();"
                )
            )


def downgrade() -> None:
    if _is_postgres():
        for table in _APPEND_ONLY_TABLES:
            op.execute(sa.text(f"DROP TRIGGER IF EXISTS {table}_no_update_delete ON {table};"))
        op.execute(sa.text("DROP FUNCTION IF EXISTS reject_mutation();"))
    op.drop_table("audit_log")
    op.drop_table("intake_answers")
    op.drop_table("consents")
    op.drop_table("users")
