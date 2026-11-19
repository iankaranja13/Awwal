"""Anthropic HTTP provider (no SDK dependency)."""

import json
from typing import Any

import httpx

from app.llm.errors import LLMError


class AnthropicProvider:
    """Generate structured output via the Anthropic messages API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout: float,
        temperature: float,
        max_tokens: int,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Store credentials and generation settings.

        Args:
            api_key: Anthropic API key.
            model: Model name.
            timeout: Default request timeout in seconds.
            temperature: Sampling temperature.
            max_tokens: Maximum output tokens.
            transport: Optional HTTP transport (tests inject mocks).
        """
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.transport = transport

    def generate(
        self, system: str, user_json: dict[str, Any], json_schema: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Generate one structured JSON document.

        Args:
            system: System prompt text.
            user_json: Structured job input.
            json_schema: Expected output schema (sent as guidance).
            timeout: Request timeout in seconds.

        Returns:
            Parsed JSON document.

        Raises:
            LLMError: If the request fails or the output is unusable.
        """
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Input JSON:\n"
                        + json.dumps(user_json)
                        + "\n\nRespond with JSON matching this schema:\n"
                        + json.dumps(json_schema)
                    ),
                }
            ],
            "temperature": self.temperature,
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        try:
            with httpx.Client(transport=self.transport, timeout=timeout) as client:
                response = client.post(
                    "https://api.anthropic.com/v1/messages", json=payload, headers=headers
                )
        except httpx.TimeoutException as exc:
            raise LLMError("LLM request timed out.") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM request failed: {exc}.") from exc
        if response.status_code != 200:
            raise LLMError(f"LLM provider returned status {response.status_code}.")
        try:
            data = response.json()
        except ValueError as exc:
            raise LLMError("LLM provider returned invalid JSON.") from exc
        try:
            text = data["content"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("LLM provider returned an unexpected shape.") from exc
        if not isinstance(text, str):
            raise LLMError("LLM provider returned an unexpected shape.")
        try:
            parsed: Any = json.loads(text)
        except ValueError as exc:
            raise LLMError("LLM output was not valid JSON.") from exc
        if not isinstance(parsed, dict):
            raise LLMError("LLM output was not a JSON object.")
        return parsed
