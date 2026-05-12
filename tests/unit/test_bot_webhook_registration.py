from __future__ import annotations

import fcntl
from pathlib import Path

import pytest

from core.config import Settings
from features.bot.service import BotService, register_webhook


def _settings() -> Settings:
    return Settings(
        DB_USER="test",
        DB_PASSWORD="test",
        BOT_TOKEN="test-token",
        KIMI_CODE_API_KEY="test-key",
        PUBLIC_API_BASE_URL="https://api.example.com",
    )


@pytest.mark.asyncio
async def test_register_webhook_skips_recent_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    lock_path = tmp_path / "webhook.lock"
    monkeypatch.setenv("PHANGAN_API_WEBHOOK_LOCK_PATH", str(lock_path))
    monkeypatch.setenv("PHANGAN_API_WEBHOOK_COOLDOWN_S", "60")

    calls: list[str] = []

    async def fake_register(self: BotService, base_url: str) -> bool:
        calls.append(base_url)
        return True

    monkeypatch.setattr(BotService, "register_webhook_url", fake_register)

    assert await register_webhook(_settings()) is True
    assert await register_webhook(_settings()) is True

    assert calls == ["https://api.example.com"]


@pytest.mark.asyncio
async def test_register_webhook_skips_when_another_worker_holds_lock(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    lock_path = tmp_path / "webhook.lock"
    lock_path.touch()
    monkeypatch.setenv("PHANGAN_API_WEBHOOK_LOCK_PATH", str(lock_path))

    calls: list[str] = []

    async def fake_register(self: BotService, base_url: str) -> bool:
        calls.append(base_url)
        return True

    monkeypatch.setattr(BotService, "register_webhook_url", fake_register)

    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            assert await register_webhook(_settings()) is False
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    assert calls == []
