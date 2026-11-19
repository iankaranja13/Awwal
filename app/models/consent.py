"""Append-only consent ledger model."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.enums import ConsentScope
from app.models.base import Base
from app.models.types import AwareDateTime


class Consent(Base):
    """One consent grant or revocation (never updated or deleted)."""

    __tablename__ = "consents"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('intake', 'share_with_clinician', 'reminders', 'aggregate_analytics')",
            name="ck_consents_scope",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    scope: Mapped[ConsentScope] = mapped_column(
        SAEnum(
            ConsentScope,
            native_enum=False,
            validate_strings=True,
            length=32,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    granted: Mapped[bool] = mapped_column(nullable=False)
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utc_now, nullable=False)
