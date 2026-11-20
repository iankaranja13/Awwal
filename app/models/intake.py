"""Encrypted intake storage model."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.models.base import Base
from app.models.types import AwareDateTime


class IntakeAnswers(Base):
    """One encrypted answer set per user."""

    __tablename__ = "intake_answers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    answers_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        AwareDateTime, default=utc_now, onupdate=utc_now, nullable=False
    )
