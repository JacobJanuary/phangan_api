"""Anthropic provider."""

from __future__ import annotations

from dataclasses import dataclass

from anthropic import AsyncAnthropic

from core.exceptions import ExternalServiceError
from shared.ai.ports import CompletionRequest, IAIProvider


@dataclass(slots=True)
class AnthropicProvider(IAIProvider):
    """Adapter over the `anthropic` SDK."""

    api_key: str
    model: str
    name: str = "anthropic"
    _client: AsyncAnthropic | None = None

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("AnthropicProvider.api_key must be set")
        if not self.model:
            raise ValueError("AnthropicProvider.model must be set")

        self._client = AsyncAnthropic(api_key=self.api_key)

    async def complete(self, request: CompletionRequest) -> str:
        assert self._client is not None  # set in __post_init__
        try:
            response = await self._client.messages.create(
                model=self.model,
                max_tokens=request.max_tokens,
                system=request.system,
                messages=[{"role": "user", "content": request.user}],
            )
        except Exception as exc:  # SDK raises a wide range of errors
            raise ExternalServiceError(
                f"Anthropic SDK error: {exc}", details={"provider": self.name, "model": self.model}
            ) from exc

        if not response.content or not response.content[0].text:
            raise ExternalServiceError(
                "Empty response from Anthropic",
                details={"provider": self.name, "model": self.model},
            )
        return response.content[0].text.strip()
