"""Vibe Pilot provider cascade."""

import pytest

from core.config import Constants, Settings
from core.exceptions import ExternalServiceError
from features.planner.service import PlannerService


def _service(**settings: object) -> PlannerService:
    return PlannerService(
        pool=None,  # type: ignore[arg-type]
        settings=Settings(DB_USER="test", DB_PASSWORD="test", BOT_TOKEN="bot:test", **settings),  # type: ignore[arg-type]
        constants=Constants(),
    )


def test_cascade_uses_anthropic() -> None:
    cascade = _service(ANTHROPIC_API_KEY="test")._build_cascade()

    assert [step.provider.name for step in cascade.steps] == ["anthropic_true"]


def test_cascade_without_anthropic_key_names_the_setting() -> None:
    with pytest.raises(ExternalServiceError) as exc:
        _service(ANTHROPIC_API_KEY=None)._build_cascade()

    assert exc.value.details == {"hint": "set ANTHROPIC_API_KEY"}
