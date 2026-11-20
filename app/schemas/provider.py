"""Provider response models."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import ReferralType


class ProviderOut(BaseModel):
    """One provider directory entry."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(description="Provider id.")
    name: str = Field(description="Provider name.")
    type: ReferralType = Field(description="Service type.")
    languages: list[str] = Field(description="Supported languages.")
    clinician_gender: str = Field(description="Clinician gender.")
    tele: bool = Field(description="Whether teleconsult is offered.")
    home_sampling: bool = Field(description="Whether home sampling is offered.")
    notes: str = Field(description="Notes.")
    mock: bool = Field(description="Whether this is a mock provider.")
