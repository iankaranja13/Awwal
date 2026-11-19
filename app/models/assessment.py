"""Assessment result model."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, ForeignKey, String, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.enums import Route
from app.models.base import Base
from app.models.types import AwareDateTime


class Assessment(Base):
    """One persisted triage assessment."""

    __tablename__ = "assessments"
    __table_args__ = (
        CheckConstraint(
            "route IN ('URGENT', 'ANDROLOGY_UROLOGY', 'FERTILITY_SERVICES', "
            "'PRIMARY_CARE', 'SELF_CARE', 'SELF_CARE_PROVISIONAL')",
            name="ck_assessments_route",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    rules_version: Mapped[str] = mapped_column(String(16), nullable=False)
    flags: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    missing_items: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    route: Mapped[Route] = mapped_column(
        SAEnum(
            Route,
            native_enum=False,
            validate_strings=True,
            length=32,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    route_reason: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    urgent: Mapped[bool] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utc_now, nullable=False)
