"""OpenAI-compatible provider (covers DeepSeek, OpenAI, etc. via base_url)."""

from __future__ import annotations

from dataclasses import dataclass

from openai import AsyncOpenAI

from core.exceptions import ExternalServiceError
from shared.ai.ports import CompletionRequest, IAIProvider


@dataclass(slots=True)
class OpenAICompatibleProvider(IAIProvider):
    """Adapter over the `openai` SDK targeting any `/v1/chat/completions` endpoint."""

    api_key: str
    model: str
    name: str = "openai"
    base_url: str | None = None
    _client: AsyncOpenAI | None = None

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("OpenAICompatibleProvider.api_key must be set")
        if not self.model:
            raise ValueError("OpenAICompatibleProvider.model must be set")

        kwargs: dict[str, object] = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self._client = AsyncOpenAI(**kwargs)  # type: ignore[arg-type]

    async def complete(self, request: CompletionRequest) -> str:
        assert self._client is not None
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                max_tokens=request.max_tokens,
                messages=[
                    {"role": "system", "content": request.system},
                    {"role": "user", "content": request.user},
                ],
            )
        except Exception as exc:
            raise ExternalServiceError(
                f"OpenAI-compatible SDK error: {exc}",
                details={"provider": self.name, "model": self.model},
            ) from exc

        if not response.choices or not response.choices[0].message.content:
            raise ExternalServiceError(
                "Empty response from OpenAI-compatible provider",
                details={"provider": self.name, "model": self.model},
            )
        return response.choices[0].message.content.strip()
