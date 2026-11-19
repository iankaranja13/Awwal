"""LLM client factory and provider behaviour."""

import json
from typing import Any

import httpx
import pytest

from app.core.config import Settings
from app.llm.client import PROMPT_VERSION, create_client, load_prompt
from app.llm.errors import LLMError
from app.llm.providers.anthropic import AnthropicProvider
from app.llm.providers.mock import MockProvider
from app.llm.providers.openai_compatible import OpenAICompatibleProvider
from app.schemas.explain import ExplainerOutput
from tests.unit.rule_helpers import APP_CONTENT_DIR


def _settings(**overrides: Any) -> Settings:
    from cryptography.fernet import Fernet

    values: dict[str, Any] = {
        "jwt_secret": "test-secret-for-unit-tests",
        "field_encryption_key": Fernet.generate_key().decode("utf-8"),
    }
    values.update(overrides)
    return Settings(**values)


def _explain_input() -> dict[str, Any]:
    return {
        "job": "explain",
        "language": "en",
        "route": "PRIMARY_CARE",
        "route_reason": ["MB_DIABETES"],
        "flags": [
            {
                "flag_id": "MB_DIABETES",
                "state": "PRESENT",
                "label": "Diabetes",
                "snippet_id": "SNP_DIABETES",
                "modifiable": True,
                "unknowns": [],
                "reason_fields": ["diabetes"],
            }
        ],
        "missing_items": [],
        "next_step_text": "Book a primary-care appointment.",
        "disclaimer": "This is a screening tool, not a diagnosis.",
    }


def test_mock_output_is_valid_and_deterministic() -> None:
    """Return valid identical outputs for identical inputs."""
    provider = MockProvider(content_dir=str(APP_CONTENT_DIR))
    first = provider.generate("system", _explain_input(), {}, 8.0)
    second = provider.generate("system", _explain_input(), {}, 8.0)
    assert first == second
    parsed = ExplainerOutput.model_validate(first)
    assert parsed.language.value == "en"
    assert parsed.flags[0].flag_id == "MB_DIABETES"


def test_mock_builds_briefs() -> None:
    """Build brief-shaped outputs for brief jobs."""
    from app.schemas.explain import BriefOutput

    provider = MockProvider(content_dir=str(APP_CONTENT_DIR))
    output = provider.generate(
        "system",
        {
            "job": "brief",
            "language": "en",
            "route": "PRIMARY_CARE",
            "route_reason": ["MB_DIABETES"],
            "reason_hint": "Diabetes review.",
            "rationale_hint": "Routine.",
            "flags": [
                {
                    "flag_id": "MB_DIABETES",
                    "state": "PRESENT",
                    "label": "Diabetes",
                    "source": "TO BE CONFIRMED",
                }
            ],
            "missing_information": [],
            "scope_note": "Owner view.",
        },
        {},
        8.0,
    )
    assert BriefOutput.model_validate(output).route.value == "PRIMARY_CARE"


def test_factory_defaults_to_mock() -> None:
    """Create the mock provider by default."""
    assert isinstance(create_client(_settings()), MockProvider)


def test_factory_rejects_unconfigured_providers() -> None:
    """Fail fast when real providers lack configuration."""
    with pytest.raises(LLMError, match="LLM_API_KEY"):
        create_client(_settings(llm_provider="anthropic"))
    with pytest.raises(LLMError, match="LLM_BASE_URL"):
        create_client(_settings(llm_provider="openai_compatible", llm_model="local"))


def test_load_prompt_reads_versioned_files() -> None:
    """Load versioned prompts and fail clearly when missing."""
    assert PROMPT_VERSION == "v1"
    assert "screening" in load_prompt("explain").lower()
    assert "brief" in load_prompt("brief").lower()
    with pytest.raises(LLMError, match="Cannot read prompt"):
        load_prompt("nope")


def _anthropic(handler: Any) -> AnthropicProvider:
    return AnthropicProvider(
        api_key="key",
        model="model",
        timeout=8.0,
        temperature=0.2,
        max_tokens=10,
        transport=httpx.MockTransport(handler),
    )


def test_anthropic_success() -> None:
    """Parse successful Anthropic responses."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/messages"
        assert request.headers["x-api-key"] == "key"
        return httpx.Response(200, json={"content": [{"text": '{"ok": true}'}]})

    provider = _anthropic(handler)
    assert provider.generate("sys", {"a": 1}, {}, 8.0) == {"ok": True}


def test_anthropic_sends_model_settings() -> None:
    """Send model, temperature and limits to Anthropic."""
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json={"content": [{"text": "{}"}]})

    _anthropic(handler).generate("sys", {}, {}, 8.0)
    assert captured["model"] == "model"
    assert captured["temperature"] == 0.2
    assert captured["max_tokens"] == 10


def test_anthropic_failures() -> None:
    """Map Anthropic failures to LLMError."""
    cases = [
        (httpx.Response(500, json={}), "status 500"),
        (httpx.Response(200, content=b"nope"), "invalid JSON"),
        (httpx.Response(200, json={"nope": 1}), "unexpected shape"),
        (httpx.Response(200, json={"content": [{"text": "nope"}]}), "not valid JSON"),
        (httpx.Response(200, json={"content": [{"text": "[1]"}]}), "not a JSON object"),
    ]
    for response, match in cases:

        def handler(request: httpx.Request, response: httpx.Response = response) -> httpx.Response:
            return response

        with pytest.raises(LLMError, match=match):
            _anthropic(handler).generate("sys", {}, {}, 8.0)


def test_anthropic_timeout() -> None:
    """Map timeouts to LLMError."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("slow")

    with pytest.raises(LLMError, match="timed out"):
        _anthropic(handler).generate("sys", {}, {}, 8.0)


def test_openai_success_and_shape() -> None:
    """Parse OpenAI-compatible responses and omit empty keys."""
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": 1}'}}]})

    provider = OpenAICompatibleProvider(
        api_key="",
        model="local",
        base_url="http://localhost:9999/v1/",
        timeout=8.0,
        temperature=0.1,
        max_tokens=5,
        transport=httpx.MockTransport(handler),
    )
    assert provider.generate("sys", {}, {}, 8.0) == {"ok": 1}
    assert "authorization" not in captured["headers"]


def test_openai_failures() -> None:
    """Map OpenAI-compatible failures to LLMError."""
    cases = [
        (httpx.Response(500, json={}), "status 500"),
        (httpx.Response(200, json={"x": 1}), "unexpected shape"),
    ]
    for response, match in cases:

        def handler(request: httpx.Request, response: httpx.Response = response) -> httpx.Response:
            return response

        provider = OpenAICompatibleProvider(
            api_key="k",
            model="m",
            base_url="http://x",
            timeout=8.0,
            temperature=0.2,
            max_tokens=5,
            transport=httpx.MockTransport(handler),
        )
        with pytest.raises(LLMError, match=match):
            provider.generate("sys", {}, {}, 8.0)
