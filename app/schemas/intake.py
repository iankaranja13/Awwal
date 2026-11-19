"""Intake schema, answer and response models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import ItemStatus, ItemType
from app.rules_engine.models import Label


class ItemOption(BaseModel):
    """One selectable option for a choice item."""

    model_config = ConfigDict(frozen=True)

    value: str = Field(min_length=1, description="Stored option value.")
    label: Label = Field(description="Bilingual display label.")


class IntakeItem(BaseModel):
    """One intake schema item."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, description="Stable item id.")
    domain: str = Field(min_length=1, description="Clinical domain.")
    type: ItemType = Field(description="Answer type.")
    required_for_flags: list[str] = Field(default_factory=list, description="Rules using this item.")
    label: Label = Field(description="Bilingual question text.")
    why_we_ask: Label = Field(description="Bilingual reason for asking.")
    options: list[ItemOption] = Field(default_factory=list, description="Choice options.")
    sensitive: bool = Field(description="Whether the item holds sensitive content.")
    optional_by_design: bool = Field(description="Whether the item is optional by design.")
    needs_native_review: bool = Field(description="True until Arabic review exists.")
    min_value: float | None = Field(default=None, description="Minimum for number items.")
    max_value: float | None = Field(default=None, description="Maximum for number items.")
    max_length: int | None = Field(default=None, description="Maximum length for text items.")


class IntakeSchemaDocument(BaseModel):
    """Versioned intake schema document."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = Field(min_length=1, description="Schema version.")
    items: list[IntakeItem] = Field(description="Schema items.")


class AnswerIn(BaseModel):
    """One submitted answer."""

    model_config = ConfigDict(frozen=True)

    value: Any = Field(default=None, description="Provided answer value.")
    status: ItemStatus = Field(description="Answer status.")


class IntakeUpdateRequest(BaseModel):
    """Partial or full intake answers update."""

    model_config = ConfigDict(frozen=True)

    answers: dict[str, AnswerIn] = Field(description="Answers by item id.")


class IntakeResponse(BaseModel):
    """Intake save receipt."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = Field(description="Schema version stored.")
    saved_item_ids: list[str] = Field(description="Item ids saved from this request.")
    updated_at: datetime = Field(description="Storage timestamp (UTC).")


class IntakeGetResponse(BaseModel):
    """Decrypted stored intake answers."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = Field(description="Schema version stored.")
    answers: dict[str, AnswerIn] = Field(description="Answers by item id.")
    updated_at: datetime | None = Field(description="Storage timestamp (UTC), if ever saved.")
