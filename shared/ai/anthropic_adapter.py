"""Anthropic-compatible provider (also covers Kimi via custom base_url)."""

from __future__ import annotations

from dataclasses import dataclass

from anthropic import AsyncAnthropic

from core.exceptions import ExternalServiceError
from shared.ai.ports import CompletionRequest, IAIProvider


@dataclass(slots=True)
class AnthropicProvider(IAIProvider):
    """Adapter over the `anthropic` SDK.

    Pass a custom `base_url` to target Kimi's `claude-code` endpoint while
    keeping the same wire protocol.
    """

    api_key: str
    model: str
    name: str = "anthropic"
    base_url: str | None = None
    user_agent: str | None = None
    _client: AsyncAnthropic | None = None

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("AnthropicProvider.api_key must be set")
        if not self.model:
            raise ValueError("AnthropicProvider.model must be set")

        kwargs: dict[str, object] = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        if self.user_agent:
            kwargs["default_headers"] = {"User-Agent": self.user_agent}
        self._client = AsyncAnthropic(**kwargs)  # type: ignore[arg-type]

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
                "Empty response from Anthropic-compatible provider",
                details={"provider": self.name, "model": self.model},
            )
        return response.content[0].text.strip()
