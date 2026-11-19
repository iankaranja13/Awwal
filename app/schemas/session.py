"""Session request and response models."""

from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import Language, Role


class SessionRequest(BaseModel):
    """Anonymous session creation request."""

    language: Language = Field(default=Language.EN, description="Preferred interface language.")


class SessionResponse(BaseModel):
    """Created session with access token."""

    user_id: UUID = Field(description="User id.")
    handle: str = Field(description="Pseudonymous handle.")
    role: Role = Field(description="Caller role.")
    token: str = Field(description="Bearer access token.")
