"""Explanation record model."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, ForeignKey, String, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.enums import ExplanationSource, Language
from app.models.base import Base
from app.models.types import AwareDateTime


class Explanation(Base):
    """One stored explanation for an assessment."""

    __tablename__ = "explanations"
    __table_args__ = (
        CheckConstraint("language IN ('en', 'ar')", name="ck_explanations_language"),
        CheckConstraint(
            "source IN ('llm', 'template', 'static')", name="ck_explanations_source"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessments.id"), index=True)
    language: Mapped[Language] = mapped_column(
        SAEnum(
            Language,
            native_enum=False,
            validate_strings=True,
            length=8,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    source: Mapped[ExplanationSource] = mapped_column(
        SAEnum(
            ExplanationSource,
            native_enum=False,
            validate_strings=True,
            length=16,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    text: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    validator_result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utc_now, nullable=False)
