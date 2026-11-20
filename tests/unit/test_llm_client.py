"""LLM client factory and provider behaviour."""

import json
from typing import Any

import httpx
import pytest

from app.core.config import Settings
from app.llm.client import PROMPT_VERSION, create_client, load_prompt
from app.llm.errors import LLMError
from app.llm.providers.anthropic import AnthropicProvider
from app.llm.providers.azure_openai import AzureOpenAIProvider
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
    assert PROMPT_VERSION == "v2"
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


def test_azure_sends_key_header_and_versioned_url() -> None:
    """Use api-key auth and the api-version query on the deployment URL."""
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["url"] = request.url
        body = json.loads(request.content.decode("utf-8"))
        captured["model"] = body["model"]
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": 1}'}}]})

    provider = AzureOpenAIProvider(
        api_key="az-key",
        model="awwal-gpt",
        base_url="https://res.openai.azure.com/openai/deployments/awwal-gpt/",
        api_version="2024-10-21",
        timeout=8.0,
        temperature=0.2,
        max_tokens=5,
        transport=httpx.MockTransport(handler),
    )
    assert provider.generate("sys", {}, {}, 8.0) == {"ok": 1}
    assert captured["headers"]["api-key"] == "az-key"
    assert "authorization" not in captured["headers"]
    assert captured["url"].path == "/openai/deployments/awwal-gpt/chat/completions"
    assert captured["url"].params["api-version"] == "2024-10-21"
    assert captured["model"] == "awwal-gpt"


def test_azure_failure_maps_to_llm_error() -> None:
    """Map Azure error statuses to LLMError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={})

    provider = AzureOpenAIProvider(
        api_key="bad",
        model="m",
        base_url="https://res.openai.azure.com/openai/deployments/m",
        api_version="2024-10-21",
        timeout=8.0,
        temperature=0.2,
        max_tokens=5,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(LLMError, match="status 401"):
        provider.generate("sys", {}, {}, 8.0)


def test_factory_builds_azure_when_configured() -> None:
    """Build the Azure provider from settings."""
    client = create_client(
        _settings(
            llm_provider="azure_openai",
            llm_api_key="az-key",
            llm_model="awwal-gpt",
            llm_base_url="https://res.openai.azure.com/openai/deployments/awwal-gpt",
            llm_api_version="2024-10-21",
        )
    )
    assert isinstance(client, AzureOpenAIProvider)


def test_factory_rejects_incomplete_azure_config() -> None:
    """Require all four Azure settings before building the client."""
    base = {
        "llm_provider": "azure_openai",
        "llm_api_key": "az-key",
        "llm_model": "awwal-gpt",
        "llm_base_url": "https://res.openai.azure.com/openai/deployments/awwal-gpt",
        "llm_api_version": "2024-10-21",
    }
    for missing in ("llm_api_key", "llm_model", "llm_base_url", "llm_api_version"):
        values = {**base, missing: ""}
        with pytest.raises(LLMError, match="Azure OpenAI needs"):
            create_client(_settings(**values))


def test_mock_cites_input_excerpts() -> None:
    """Cite provided excerpt ids per flag in mock outputs."""
    provider = MockProvider(content_dir=str(APP_CONTENT_DIR))
    user_json = dict(_explain_input())
    user_json["excerpts"] = [
        {"excerpt_id": "EXC_MB_DIABETES", "text": "Draft.", "flag_ids": ["MB_DIABETES"]}
    ]
    output = provider.generate("sys", user_json, {}, 8.0)
    assert output["flags"][0]["sources"] == ["EXC_MB_DIABETES"]
