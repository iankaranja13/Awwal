"""Health-check response models."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness probe response."""

    status: str = Field(default="ok", description="Service status (``ok`` when healthy).")
    version: str = Field(description="Application version.")
    environment: str = Field(description="Deployment environment name.")
