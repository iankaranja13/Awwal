"""Workflow trace record model."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.models.base import Base
from app.models.types import AwareDateTime


class WorkflowTrace(Base):
    """One persisted pipeline trace per assessment."""

    __tablename__ = "workflow_traces"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id"), unique=True, index=True
    )
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utc_now, nullable=False)
