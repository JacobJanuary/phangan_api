"""AI cascade orchestrator with per-provider retry."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from core.exceptions import ExternalServiceError
from shared.ai.ports import CompletionRequest, IAIProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CascadeStep:
    """One step in a fallback cascade."""

    provider: IAIProvider
    max_attempts: int = 1
    backoff_seconds: float = 1.0


@dataclass(slots=True)
class CascadeOrchestrator:
    """Run a request against an ordered list of providers with retries.

    Behaviour:
      1. For each step, call `provider.complete` up to `max_attempts` times.
      2. On any exception, log a warning and retry after `backoff_seconds`.
      3. If all attempts for a step fail, move on to the next step.
      4. If every step fails, raise an `ExternalServiceError` aggregating
         the final error from each provider.
    """

    steps: list[CascadeStep]

    def __post_init__(self) -> None:
        if not self.steps:
            raise ValueError("CascadeOrchestrator requires at least one step")
        for step in self.steps:
            if step.max_attempts < 1:
                raise ValueError("CascadeStep.max_attempts must be >= 1")
            if step.backoff_seconds < 0:
                raise ValueError("CascadeStep.backoff_seconds must be >= 0")

    async def complete(self, request: CompletionRequest) -> str:
        errors: list[str] = []

        for step in self.steps:
            provider = step.provider
            last_exc: Exception | None = None

            for attempt in range(1, step.max_attempts + 1):
                try:
                    logger.info(
                        "AI cascade attempt",
                        extra={
                            "provider": provider.name,
                            "attempt": attempt,
                            "max_attempts": step.max_attempts,
                        },
                    )
                    return await provider.complete(request)
                except Exception as exc:
                    last_exc = exc
                    logger.warning(
                        "AI cascade attempt failed",
                        extra={
                            "provider": provider.name,
                            "attempt": attempt,
                            "error": str(exc)[:300],
                        },
                    )
                    if attempt < step.max_attempts and step.backoff_seconds > 0:
                        await asyncio.sleep(step.backoff_seconds)

            if last_exc is not None:
                errors.append(f"{provider.name}: {last_exc}")

        raise ExternalServiceError(
            "All AI providers in cascade failed",
            details={"errors": errors},
        )
