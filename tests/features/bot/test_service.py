"""Webhook registration when every uvicorn worker runs it at start."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from features.bot import service as bot_service
from features.bot.service import BotService

URL = "https://api.example/api/bot/webhook"


class FakeClient:
    def __init__(self, *, webhook_url="", set_results=()):
        self.webhook_url = webhook_url
        self.set_results = list(set_results)
        self.calls = []

    async def call(self, method, **payload):
        self.calls.append(method)
        if method == "getWebhookInfo":
            return {"ok": True, "result": {"url": self.webhook_url}}
        result = self.set_results.pop(0)
        if result.get("ok"):
            self.webhook_url = payload["url"]
        return result


@pytest.fixture
def client(monkeypatch):
    holder = SimpleNamespace(client=None)
    monkeypatch.setattr(BotService, "_client", property(lambda self: holder.client))

    async def no_wait(_seconds):
        return None

    monkeypatch.setattr(bot_service.asyncio, "sleep", no_wait)
    return holder


def _service():
    return BotService(settings=SimpleNamespace(BOT_TOKEN="t"))


async def test_a_webhook_already_pointing_here_is_left_alone(client, caplog):
    client.client = FakeClient(webhook_url=URL)
    with caplog.at_level(logging.INFO):
        assert await _service().register_webhook_url("https://api.example/") is True
    assert client.client.calls == ["getWebhookInfo"]
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


async def test_a_rate_limited_worker_waits_and_finds_the_webhook_set(client, caplog):
    fake = FakeClient(set_results=[{"ok": False, "error_code": 429, "parameters": {"retry_after": 1}}])
    client.client = fake
    real_call = fake.call

    async def call(method, **payload):  # another worker sets it while this one waits
        result = await real_call(method, **payload)
        if method == "setWebhook":
            fake.webhook_url = URL
        return result

    fake.call = call
    with caplog.at_level(logging.INFO):
        assert await _service().register_webhook_url("https://api.example") is True
    assert fake.calls == ["getWebhookInfo", "setWebhook", "getWebhookInfo"]
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


async def test_a_new_url_is_set_and_a_real_failure_is_logged(client, caplog):
    client.client = FakeClient(webhook_url="https://old/api/bot/webhook", set_results=[{"ok": True}])
    assert await _service().register_webhook_url("https://api.example") is True

    client.client = FakeClient(set_results=[{"ok": False, "error_code": 401, "description": "Unauthorized"}])
    with caplog.at_level(logging.ERROR):
        assert await _service().register_webhook_url("https://api.example") is False
    assert any(r.getMessage() == "Failed to register Telegram webhook" for r in caplog.records)
