"""Phase 5 tables: providers, referrals, events, reminders, reviews.

Revision ID: phase5_referrals
Revises: phase3_assessment
Create Date: 2026-11-19

Referral events join the append-only set with the same Postgres trigger.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "phase5_referrals"
down_revision: str | None = "phase3_assessment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

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
        "providers",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("languages", sa.JSON, nullable=False),
        sa.Column("clinician_gender", sa.String(16), nullable=False),
        sa.Column("tele", sa.Boolean, nullable=False),
        sa.Column("home_sampling", sa.Boolean, nullable=False),
        sa.Column("notes", sa.Text, nullable=False),
        sa.Column("mock", sa.Boolean, nullable=False),
        sa.CheckConstraint(
            "type IN ('teleconsult', 'blood_test', 'sample_collection', 'in_person')",
            name="ck_providers_type",
        ),
        sa.CheckConstraint(
            "clinician_gender IN ('male', 'female')", name="ck_providers_gender"
        ),
    )
    op.create_table(
        "referrals",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "assessment_id", sa.Uuid, sa.ForeignKey("assessments.id"), nullable=False, index=True
        ),
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("provider_id", sa.Uuid, sa.ForeignKey("providers.id"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("preferred_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("appointment_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome_note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "type IN ('teleconsult', 'blood_test', 'sample_collection', 'in_person')",
            name="ck_referrals_type",
        ),
        sa.CheckConstraint(
            "status IN ('proposed', 'clinician_review', 'confirmed', 'booked', "
            "'attended', 'result_explained', 'closed', 'cancelled', 'no_show')",
            name="ck_referrals_status",
        ),
    )
    op.create_table(
        "referral_events",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "referral_id", sa.Uuid, sa.ForeignKey("referrals.id"), nullable=False, index=True
        ),
        sa.Column("from_status", sa.String(32), nullable=True),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.Uuid, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "reminders",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "referral_id", sa.Uuid, sa.ForeignKey("referrals.id"), nullable=False, index=True
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("simulated_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "clinician_reviews",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "assessment_id",
            sa.Uuid,
            sa.ForeignKey("assessments.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("reviewer_id", sa.Uuid, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("edits", sa.JSON, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("signed_off_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('approved', 'rejected')", name="ck_reviews_decision"
        ),
    )
    if _is_postgres():
        op.execute(sa.text(_REJECT_FUNCTION))
        op.execute(
            sa.text(
                "CREATE TRIGGER referral_events_no_update_delete "
                "BEFORE UPDATE OR DELETE ON referral_events "
                "FOR EACH ROW EXECUTE FUNCTION reject_mutation();"
            )
        )


def downgrade() -> None:
    if _is_postgres():
        op.execute(
            sa.text("DROP TRIGGER IF EXISTS referral_events_no_update_delete ON referral_events;")
        )
    op.drop_table("clinician_reviews")
    op.drop_table("reminders")
    op.drop_table("referral_events")
    op.drop_table("referrals")
    op.drop_table("providers")
