"""Provider directory model (seeded mock providers)."""

import uuid

from sqlalchemy import JSON, Boolean, CheckConstraint, String, Text, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ReferralType
from app.models.base import Base


class Provider(Base):
    """Mock care provider with filter facets."""

    __tablename__ = "providers"
    __table_args__ = (
        CheckConstraint(
            "type IN ('teleconsult', 'blood_test', 'sample_collection', 'in_person')",
            name="ck_providers_type",
        ),
        CheckConstraint(
            "clinician_gender IN ('male', 'female')", name="ck_providers_gender"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[ReferralType] = mapped_column(
        SAEnum(
            ReferralType,
            native_enum=False,
            validate_strings=True,
            length=32,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    languages: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    clinician_gender: Mapped[str] = mapped_column(String(16), nullable=False)
    tele: Mapped[bool] = mapped_column(Boolean, nullable=False)
    home_sampling: Mapped[bool] = mapped_column(Boolean, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    mock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
