"""Phase 7: erasure-aware append-only triggers.

Revision ID: phase7_erase_bypass
Revises: phase6_shares
Create Date: 2026-11-20

The consents and referral-events triggers now honour a transaction-local
erasure flag: user erasure sets `awwal.erase_override` for its own
transaction so the deleted aggregate can be removed. Every other UPDATE
and DELETE stays forbidden, and self-delete still keeps consent
receipts (only a hard reset removes them with the row they reference).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "phase7_erase_bypass"
down_revision: str | None = "phase6_shares"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ERASE_GUARD_FUNCTION = """
CREATE OR REPLACE FUNCTION erase_aware_append_only_guard() RETURNS trigger AS $$
BEGIN
  IF current_setting('awwal.erase_override', true) = 'on' THEN
    IF TG_OP = 'DELETE' THEN
      RETURN OLD;
    END IF;
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'append-only table: % updates and deletes are forbidden', TG_TABLE_NAME;
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

_GUARDED_TABLES = ("consents", "referral_events")


def _is_postgres() -> bool:
    bind = op.get_bind()
    return bind is not None and bind.dialect.name == "postgresql"


def upgrade() -> None:
    if _is_postgres():
        op.execute(sa.text(_ERASE_GUARD_FUNCTION))
        for table in _GUARDED_TABLES:
            op.execute(sa.text(f"DROP TRIGGER IF EXISTS {table}_no_update_delete ON {table};"))
            op.execute(
                sa.text(
                    f"CREATE TRIGGER {table}_erase_guard "
                    f"BEFORE UPDATE OR DELETE ON {table} "
                    "FOR EACH ROW EXECUTE FUNCTION erase_aware_append_only_guard();"
                )
            )


def downgrade() -> None:
    if _is_postgres():
        for table in _GUARDED_TABLES:
            op.execute(sa.text(f"DROP TRIGGER IF EXISTS {table}_erase_guard ON {table};"))
        op.execute(sa.text("DROP FUNCTION IF EXISTS erase_aware_append_only_guard();"))
        op.execute(sa.text(_REJECT_FUNCTION))
        for table in _GUARDED_TABLES:
            op.execute(
                sa.text(
                    f"CREATE TRIGGER {table}_no_update_delete "
                    f"BEFORE UPDATE OR DELETE ON {table} "
                    "FOR EACH ROW EXECUTE FUNCTION reject_mutation();"
                )
            )
