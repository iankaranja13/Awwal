"""LLM client interface, errors and provider factory."""

from pathlib import Path
from typing import Any, Protocol

import httpx

from app.core.config import Settings
from app.llm.errors import LLMError
from app.llm.providers.anthropic import AnthropicProvider
from app.llm.providers.mock import MockProvider
from app.llm.providers.openai_compatible import OpenAICompatibleProvider

PROMPT_VERSION = "v1"


class LLMClient(Protocol):
    """Provider interface for structured generation jobs."""

    def generate(
        self, system: str, user_json: dict[str, Any], json_schema: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Generate one structured JSON document.

        Args:
            system: System prompt text.
            user_json: Structured job input (never personal data).
            json_schema: Expected output JSON schema.
            timeout: Request timeout in seconds.

        Returns:
            Parsed JSON document.

        Raises:
            LLMError: If generation fails.
        """
        ...


def load_prompt(job: str) -> str:
    """Load one versioned system prompt.

    Args:
        job: Job name (for example ``explain``).

    Returns:
        System prompt text.

    Raises:
        LLMError: If the prompt file is missing.
    """
    path = Path(__file__).resolve().parent / "prompts" / f"{job}.{PROMPT_VERSION}.txt"
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LLMError(f"Cannot read prompt file {path}: {exc.strerror}.") from exc


def create_client(settings: Settings, transport: httpx.BaseTransport | None = None) -> LLMClient:
    """Create the configured LLM client.

    Args:
        settings: Application settings.
        transport: Optional HTTP transport (tests inject mocks).

    Returns:
        Configured provider client.

    Raises:
        LLMError: If a real provider lacks its configuration.
    """
    if settings.llm_provider == "mock":
        return MockProvider(content_dir=settings.content_dir)
    if settings.llm_provider == "anthropic":
        if not settings.llm_api_key or not settings.llm_model:
            raise LLMError("Anthropic needs LLM_API_KEY and LLM_MODEL.")
        return AnthropicProvider(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout=settings.llm_timeout_seconds,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            transport=transport,
        )
    if not settings.llm_base_url or not settings.llm_model:
        raise LLMError("OpenAI-compatible needs LLM_BASE_URL and LLM_MODEL.")
    return OpenAICompatibleProvider(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout_seconds,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        transport=transport,
    )
