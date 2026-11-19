"""Bilingual content file loaders (validated, cached, fail fast)."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.enums import Language


class ContentError(Exception):
    """Content files are missing or invalid."""


class SafetyMessage(BaseModel):
    """One static safety message."""

    model_config = ConfigDict(frozen=True)

    title: str = Field(min_length=1, description="Message title.")
    body: str = Field(min_length=1, description="Message body.")


class StaticSafetyFile(BaseModel):
    """Static safety content file."""

    model_config = ConfigDict(frozen=True)

    needs_native_review: bool = Field(description="True until Arabic review exists.")
    messages: dict[str, SafetyMessage] = Field(description="Messages by id.")


class SnippetsFile(BaseModel):
    """Flag snippet content file."""

    model_config = ConfigDict(frozen=True)

    needs_native_review: bool = Field(description="True until Arabic review exists.")
    snippets: dict[str, str] = Field(description="Snippet text by id.")


class NextStepsFile(BaseModel):
    """Next-step content file."""

    model_config = ConfigDict(frozen=True)

    needs_native_review: bool = Field(description="True until Arabic review exists.")
    steps: dict[str, str] = Field(description="Next-step text by route.")


class ExplainerFile(BaseModel):
    """Template explainer strings file."""

    model_config = ConfigDict(frozen=True)

    needs_native_review: bool = Field(description="True until Arabic review exists.")
    disclaimer: str = Field(min_length=1, description="Screening disclaimer.")
    summary_signals: str = Field(min_length=1, description="Summary with {count} signals.")
    summary_provisional: str = Field(description="Summary for incomplete screening.")
    summary_clear: str = Field(description="Summary for no signals.")
    modifiable_note: str = Field(min_length=1, description="Modifiable factor note.")
    brief_scope_owner: str = Field(min_length=1, description="Owner-view scope note.")
    brief_rationale_prefix: str = Field(min_length=1, description="Route rationale prefix.")
    brief_rationale_none: str = Field(min_length=1, description="Rationale when undriven.")


def _load_json(content_dir: str, name: str) -> Any:
    """Read and parse one content file.

    Args:
        content_dir: Content directory.
        name: File name.

    Returns:
        Parsed JSON document.

    Raises:
        ContentError: If the file is missing or malformed.
    """
    path = Path(content_dir) / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ContentError(f"Cannot read content file {path}: {exc.strerror}.") from exc
    except ValueError as exc:
        raise ContentError(f"Invalid JSON in {path}: {exc}.") from exc


ContentFileT = TypeVar("ContentFileT", bound=BaseModel)


def _parse(name: str, model: type[ContentFileT], raw: Any) -> ContentFileT:
    """Validate one document against its model.

    Args:
        name: File name (for error messages).
        model: Pydantic model.
        raw: Parsed JSON document.

    Returns:
        Validated document.

    Raises:
        ContentError: If validation fails.
    """
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        raise ContentError(f"Invalid content file {name}: {exc}.") from exc


def _require_review(name: str, marked: bool) -> None:
    """Reject content that drops the native-review marker.

    Args:
        name: File name (for error messages).
        marked: Marker value.

    Raises:
        ContentError: If the marker is false.
    """
    if marked is not True:
        raise ContentError(f"Content file {name} must keep needs_native_review.")


@lru_cache(maxsize=16)
def load_static_safety(content_dir: str, language: Language) -> StaticSafetyFile:
    """Load static safety messages for one language.

    Args:
        content_dir: Content directory.
        language: Language to load.

    Returns:
        Validated safety messages.

    Raises:
        ContentError: If the file is missing or invalid.
    """
    raw = _load_json(content_dir, f"static_safety.{language.value}.json")
    loaded = _parse("static_safety", StaticSafetyFile, raw)
    _require_review("static_safety", loaded.needs_native_review)
    return loaded


@lru_cache(maxsize=16)
def load_snippets(content_dir: str, language: Language) -> SnippetsFile:
    """Load flag snippets for one language.

    Args:
        content_dir: Content directory.
        language: Language to load.

    Returns:
        Validated snippets.

    Raises:
        ContentError: If the file is missing or invalid.
    """
    raw = _load_json(content_dir, f"snippets.{language.value}.json")
    loaded = _parse("snippets", SnippetsFile, raw)
    _require_review("snippets", loaded.needs_native_review)
    return loaded


@lru_cache(maxsize=16)
def load_next_steps(content_dir: str, language: Language) -> NextStepsFile:
    """Load next-step texts for one language.

    Args:
        content_dir: Content directory.
        language: Language to load.

    Returns:
        Validated next steps.

    Raises:
        ContentError: If the file is missing or invalid.
    """
    raw = _load_json(content_dir, f"next_steps.{language.value}.json")
    loaded = _parse("next_steps", NextStepsFile, raw)
    _require_review("next_steps", loaded.needs_native_review)
    return loaded


@lru_cache(maxsize=16)
def load_explainer(content_dir: str, language: Language) -> ExplainerFile:
    """Load template explainer strings for one language.

    Args:
        content_dir: Content directory.
        language: Language to load.

    Returns:
        Validated explainer strings.

    Raises:
        ContentError: If the file is missing or invalid.
    """
    raw = _load_json(content_dir, f"explainer.{language.value}.json")
    loaded = _parse("explainer", ExplainerFile, raw)
    _require_review("explainer", loaded.needs_native_review)
    return loaded
