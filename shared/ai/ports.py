"""AI provider port (hexagonal boundary).

Concrete adapters wrap vendor SDKs. The orchestrator (`cascade.py`)
depends only on this Protocol so it can mix providers freely.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CompletionRequest:
    """A single text-completion request.

    `system` is the system prompt; `user` is the user message. We deliberately
    keep the surface small — features that need richer chat histories should
    add a separate port.
    """

    system: str
    user: str
    max_tokens: int = 4096


class IAIProvider(Protocol):
    """Adapter for any text-completion AI vendor."""

    name: str

    async def complete(self, request: CompletionRequest) -> str:
        """Return the model's text response.

        Adapters MUST raise on transport errors, empty responses, or invalid
        SDK results so the orchestrator can decide whether to retry or
        cascade. They MUST NOT swallow errors.
        """
        ...
