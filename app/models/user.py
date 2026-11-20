"""User account model."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, String, Text, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.enums import Language, Role
from app.models.base import Base
from app.models.types import AwareDateTime


class User(Base):
    """Pseudonymous user account (all roles)."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'navigator', 'clinician')", name="ck_users_role"),
        CheckConstraint("language IN ('en', 'ar')", name="ck_users_language"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    pseudonymous_handle: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    role: Mapped[Role] = mapped_column(
        SAEnum(
            Role,
            native_enum=False,
            validate_strings=True,
            length=16,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
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
    contact_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utc_now, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)
