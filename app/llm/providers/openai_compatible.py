"""OpenAI-compatible HTTP provider (local servers or hosted APIs)."""

import json
from typing import Any

import httpx

from app.llm.errors import LLMError


class OpenAICompatibleProvider:
    """Generate structured output via a chat-completions endpoint."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout: float,
        temperature: float,
        max_tokens: int,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Store endpoint settings.

        Args:
            api_key: API key (may be empty for local servers).
            model: Model name.
            base_url: Server base URL.
            timeout: Default request timeout in seconds.
            temperature: Sampling temperature.
            max_tokens: Maximum output tokens.
            transport: Optional HTTP transport (tests inject mocks).
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
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
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": (
                        "Input JSON:\n"
                        + json.dumps(user_json)
                        + "\n\nRespond with JSON matching this schema:\n"
                        + json.dumps(json_schema)
                    ),
                },
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
        }
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["authorization"] = f"Bearer {self.api_key}"
        try:
            with httpx.Client(transport=self.transport, timeout=timeout) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions", json=payload, headers=headers
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
            text = data["choices"][0]["message"]["content"]
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
