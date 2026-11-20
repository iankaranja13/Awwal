"""Azure OpenAI provider (api-key auth with a versioned deployment URL)."""

import httpx

from app.llm.providers.openai_compatible import OpenAICompatibleProvider


class AzureOpenAIProvider(OpenAICompatibleProvider):
    """Generate structured output through an Azure OpenAI deployment.

    Uses ``api-key`` header auth and appends the required ``api-version``
    query parameter. The deployment in the base URL decides the model;
    ``model`` is still sent for traceability and should name it.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        api_version: str,
        timeout: float,
        temperature: float,
        max_tokens: int,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Store Azure endpoint settings.

        Args:
            api_key: Azure API key.
            model: Deployment (model) name for traceability.
            base_url: Deployment URL without the operation path, for example
                ``https://<resource>.openai.azure.com/openai/deployments/<name>``.
            api_version: Azure REST API version, for example ``2024-10-21``.
            timeout: Default request timeout in seconds.
            temperature: Sampling temperature.
            max_tokens: Maximum output tokens.
            transport: Optional HTTP transport (tests inject mocks).
        """
        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout=timeout,
            temperature=temperature,
            max_tokens=max_tokens,
            transport=transport,
        )
        self.api_version = api_version

    def _endpoint(self) -> str:
        """Return the versioned deployment chat-completions URL."""
        return f"{self.base_url}/chat/completions?api-version={self.api_version}"

    def _headers(self) -> dict[str, str]:
        """Return request headers with Azure api-key auth."""
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["api-key"] = self.api_key
        return headers
