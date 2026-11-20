"""Consent request and response models."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import ConsentScope


class ConsentRequest(BaseModel):
    """Consent grant or revocation request."""

    scope: ConsentScope = Field(description="Consent scope.")
    granted: bool = Field(description="True grants, False revokes.")


class ConsentRecord(BaseModel):
    """One ledger entry."""

    scope: ConsentScope = Field(description="Consent scope.")
    granted: bool = Field(description="True grants, False revokes.")
    policy_version: str = Field(description="Policy version in force.")
    created_at: datetime = Field(description="Entry timestamp (UTC).")


class ConsentStateResponse(BaseModel):
    """Current consent state for all scopes."""

    state: dict[ConsentScope, bool] = Field(description="Granted flag per scope.")
    policy_version: str = Field(description="Current policy version.")


class ConsentHistoryResponse(BaseModel):
    """Current consent state with full history."""

    state: dict[ConsentScope, bool] = Field(description="Granted flag per scope.")
    policy_version: str = Field(description="Current policy version.")
    history: list[ConsentRecord] = Field(description="Ledger entries oldest first.")
