"""Phase 6: shares table plus anonymisation-aware audit trigger.

Revision ID: phase6_shares
Revises: phase5_referrals
Create Date: 2026-11-19

The audit trigger now allows exactly one update shape: setting actor_id to
NULL while changing nothing else (user-erasure anonymisation). All deletes
and all other updates stay forbidden.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "phase6_shares"
down_revision: str | None = "phase5_referrals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_GUARD_FUNCTION = """
CREATE OR REPLACE FUNCTION audit_log_mutation_guard() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'append-only table: % deletes are forbidden', TG_TABLE_NAME;
  END IF;
  IF NEW.actor_id IS NOT NULL OR OLD.actor_id IS NULL THEN
    RAISE EXCEPTION 'append-only table: % updates are forbidden', TG_TABLE_NAME;
  END IF;
  IF (OLD.id, OLD.actor_role, OLD.action, OLD.object_type, OLD.object_id, OLD.at,
      OLD.detail::text)
     IS DISTINCT FROM
     (NEW.id, NEW.actor_role, NEW.action, NEW.object_type, NEW.object_id, NEW.at,
      NEW.detail::text)
  THEN
    RAISE EXCEPTION 'append-only table: % updates are forbidden', TG_TABLE_NAME;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

_REJECT_FUNCTION = """
CREATE OR REPLACE FUNCTION reject_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'append-only table: % updates and deletes are forbidden', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;
"""


def _is_postgres() -> bool:
    bind = op.get_bind()
    return bind is not None and bind.dialect.name == "postgresql"


def upgrade() -> None:
    op.create_table(
        "shares",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column(
            "recipient_id", sa.Uuid, sa.ForeignKey("users.id"), nullable=False, index=True
        ),
        sa.Column("scope", sa.JSON, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    if _is_postgres():
        op.execute(sa.text(_GUARD_FUNCTION))
        op.execute(sa.text("DROP TRIGGER IF EXISTS audit_log_no_update_delete ON audit_log;"))
        op.execute(
            sa.text(
                "CREATE TRIGGER audit_log_guarded "
                "BEFORE UPDATE OR DELETE ON audit_log "
                "FOR EACH ROW EXECUTE FUNCTION audit_log_mutation_guard();"
            )
        )


def downgrade() -> None:
    if _is_postgres():
        op.execute(sa.text("DROP TRIGGER IF EXISTS audit_log_guarded ON audit_log;"))
        op.execute(sa.text("DROP FUNCTION IF EXISTS audit_log_mutation_guard();"))
        op.execute(sa.text(_REJECT_FUNCTION))
        op.execute(
            sa.text(
                "CREATE TRIGGER audit_log_no_update_delete "
                "BEFORE UPDATE OR DELETE ON audit_log "
                "FOR EACH ROW EXECUTE FUNCTION reject_mutation();"
            )
        )
    op.drop_table("shares")
