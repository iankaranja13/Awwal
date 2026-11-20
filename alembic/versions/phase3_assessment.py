"""Phase 3 tables: assessments, explanations, workflow_traces.

Revision ID: phase3_assessment
Revises: phase2_initial
Create Date: 2026-11-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "phase3_assessment"
down_revision: str | None = "phase2_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assessments",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("rules_version", sa.String(16), nullable=False),
        sa.Column("flags", sa.JSON, nullable=False),
        sa.Column("missing_items", sa.JSON, nullable=False),
        sa.Column("route", sa.String(32), nullable=False),
        sa.Column("route_reason", sa.JSON, nullable=False),
        sa.Column("urgent", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "route IN ('URGENT', 'ANDROLOGY_UROLOGY', 'FERTILITY_SERVICES', "
            "'PRIMARY_CARE', 'SELF_CARE', 'SELF_CARE_PROVISIONAL')",
            name="ck_assessments_route",
        ),
    )
    op.create_table(
        "explanations",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "assessment_id", sa.Uuid, sa.ForeignKey("assessments.id"), nullable=False, index=True
        ),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("prompt_version", sa.String(16), nullable=True),
        sa.Column("text", sa.JSON, nullable=False),
        sa.Column("validator_result", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("language IN ('en', 'ar')", name="ck_explanations_language"),
        sa.CheckConstraint(
            "source IN ('llm', 'template', 'static')", name="ck_explanations_source"
        ),
    )
    op.create_table(
        "workflow_traces",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "assessment_id",
            sa.Uuid,
            sa.ForeignKey("assessments.id"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column("steps", sa.JSON, nullable=False),
        sa.Column("duration_ms", sa.Float, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("workflow_traces")
    op.drop_table("explanations")
    op.drop_table("assessments")
