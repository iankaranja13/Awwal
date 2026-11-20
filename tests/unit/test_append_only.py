"""Append-only enforcement for the consent ledger and audit log."""

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.enums import ConsentScope, Language, Role
from app.models import AuditLog, Consent, User

MIGRATIONS = Path(__file__).resolve().parents[2] / "alembic" / "versions"
MIGRATION = MIGRATIONS / "phase2_initial.py"
MIGRATION6 = MIGRATIONS / "phase6_shares.py"

needs_postgres = pytest.mark.skipif(
    "postgresql" not in os.environ.get("DATABASE_URL", ""),
    reason="needs a migrated Postgres database URL in DATABASE_URL",
)


def test_migration_defines_append_only_triggers() -> None:
    """Ship the Postgres triggers that reject ledger updates and deletes."""
    source = MIGRATION.read_text(encoding="utf-8")
    assert '_APPEND_ONLY_TABLES = ("consents", "audit_log")' in source
    assert "CREATE TRIGGER " in source
    assert "BEFORE UPDATE OR DELETE ON " in source
    assert "EXECUTE FUNCTION reject_mutation()" in source
    assert "DROP TRIGGER IF EXISTS " in source
    assert "DROP FUNCTION IF EXISTS reject_mutation()" in source


def test_migration_defines_audit_guard_trigger() -> None:
    """Ship the audit trigger that allows anonymisation only."""
    source = MIGRATION6.read_text(encoding="utf-8")
    assert "audit_log_guarded" in source
    assert "NEW.actor_id IS NOT NULL" in source
    assert "DROP TRIGGER IF EXISTS audit_log_guarded" in source


def test_migration_defines_erase_aware_triggers() -> None:
    """Ship the transaction-local erasure override for guarded tables."""
    source = (MIGRATIONS / "phase7_erase_bypass.py").read_text(encoding="utf-8")
    assert "erase_aware_append_only_guard" in source
    assert "current_setting('awwal.erase_override', true)" in source
    assert '_GUARDED_TABLES = ("consents", "referral_events")' in source
    assert 'down_revision: str | None = "phase6_shares"' in source


@needs_postgres
def test_consents_reject_update_and_delete() -> None:
    """Block UPDATE and DELETE on consents in Postgres (migrated first)."""
    engine = create_engine(os.environ["DATABASE_URL"])
    session = Session(engine)
    try:
        user = User(pseudonymous_handle="user-append-only", role=Role.USER, language=Language.EN)
        session.add(user)
        session.flush()
        entry = Consent(
            user_id=user.id, scope=ConsentScope.INTAKE, granted=True, policy_version="v1"
        )
        session.add(entry)
        session.flush()
        savepoint = session.begin_nested()
        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(text("UPDATE consents SET granted = NOT granted"))
            session.flush()
        savepoint.rollback()
        savepoint = session.begin_nested()
        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(text("DELETE FROM consents"))
            session.flush()
        savepoint.rollback()
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@needs_postgres
def test_audit_log_allows_anonymisation_only() -> None:
    """Allow nulling actor_id but nothing else on audit_log in Postgres."""
    engine = create_engine(os.environ["DATABASE_URL"])
    session = Session(engine)
    try:
        user = User(
            pseudonymous_handle="user-audit-anonymise",
            role=Role.USER,
            language=Language.EN,
        )
        session.add(user)
        session.flush()
        entry = AuditLog(
            actor_id=user.id,
            actor_role="user",
            action="test.ping",
            object_type="test",
            detail={},
        )
        session.add(entry)
        session.flush()
        session.execute(text("UPDATE audit_log SET actor_id = NULL"))
        session.flush()
        savepoint = session.begin_nested()
        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(text("UPDATE audit_log SET action = 'test.pong'"))
            session.flush()
        savepoint.rollback()
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@needs_postgres
def test_audit_log_rejects_update_and_delete() -> None:
    """Block UPDATE and DELETE on audit_log in Postgres (migrated first)."""
    engine = create_engine(os.environ["DATABASE_URL"])
    session = Session(engine)
    try:
        entry = AuditLog(
            actor_id=None, actor_role="user", action="test.ping", object_type="test", detail={}
        )
        session.add(entry)
        session.flush()
        savepoint = session.begin_nested()
        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(text("UPDATE audit_log SET action = 'test.pong'"))
            session.flush()
        savepoint.rollback()
        savepoint = session.begin_nested()
        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(text("DELETE FROM audit_log"))
            session.flush()
        savepoint.rollback()
    finally:
        session.rollback()
        session.close()
        engine.dispose()
