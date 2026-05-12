"""Tests for `shared.ai.cascade.CascadeOrchestrator`."""

from dataclasses import dataclass, field

import pytest

from core.exceptions import ExternalServiceError
from shared.ai.cascade import CascadeOrchestrator, CascadeStep
from shared.ai.ports import CompletionRequest, IAIProvider


@dataclass
class _FakeProvider(IAIProvider):
    """Test double — returns a queued sequence of results/exceptions."""

    name: str
    responses: list[str | Exception] = field(default_factory=list)
    calls: int = 0

    async def complete(self, request: CompletionRequest) -> str:
        self.calls += 1
        if not self.responses:
            raise RuntimeError("no responses queued")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


REQ = CompletionRequest(system="sys", user="hello")


@pytest.mark.asyncio
async def test_first_provider_succeeds_no_fallback() -> None:
    p1 = _FakeProvider(name="primary", responses=["ok"])
    p2 = _FakeProvider(name="secondary", responses=["never"])
    orch = CascadeOrchestrator(steps=[CascadeStep(p1), CascadeStep(p2)])
    assert await orch.complete(REQ) == "ok"
    assert p1.calls == 1
    assert p2.calls == 0


@pytest.mark.asyncio
async def test_retries_within_step_then_succeeds() -> None:
    p1 = _FakeProvider(name="primary", responses=[RuntimeError("flaky"), "ok"])
    orch = CascadeOrchestrator(
        steps=[CascadeStep(p1, max_attempts=2, backoff_seconds=0)]
    )
    assert await orch.complete(REQ) == "ok"
    assert p1.calls == 2


@pytest.mark.asyncio
async def test_falls_back_to_next_provider_after_exhaustion() -> None:
    p1 = _FakeProvider(name="primary", responses=[RuntimeError("a"), RuntimeError("b")])
    p2 = _FakeProvider(name="secondary", responses=["recovered"])
    orch = CascadeOrchestrator(
        steps=[
            CascadeStep(p1, max_attempts=2, backoff_seconds=0),
            CascadeStep(p2, max_attempts=1),
        ]
    )
    assert await orch.complete(REQ) == "recovered"
    assert p1.calls == 2
    assert p2.calls == 1


@pytest.mark.asyncio
async def test_all_fail_raises_external_service_error() -> None:
    p1 = _FakeProvider(name="primary", responses=[RuntimeError("a")])
    p2 = _FakeProvider(name="secondary", responses=[RuntimeError("b")])
    orch = CascadeOrchestrator(
        steps=[CascadeStep(p1, backoff_seconds=0), CascadeStep(p2, backoff_seconds=0)]
    )
    with pytest.raises(ExternalServiceError) as excinfo:
        await orch.complete(REQ)
    assert "primary" in str(excinfo.value.details)
    assert "secondary" in str(excinfo.value.details)


def test_validation_rejects_empty_steps() -> None:
    with pytest.raises(ValueError):
        CascadeOrchestrator(steps=[])


def test_validation_rejects_zero_attempts() -> None:
    p = _FakeProvider(name="x")
    with pytest.raises(ValueError):
        CascadeOrchestrator(steps=[CascadeStep(p, max_attempts=0)])
