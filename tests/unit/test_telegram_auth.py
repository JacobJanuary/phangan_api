"""Tests for `shared.telegram.auth.validate_init_data`."""

import hashlib
import hmac
import json
import urllib.parse

import pytest

from core.exceptions import AuthenticationError, ValidationError
from shared.telegram.auth import validate_init_data


BOT_TOKEN = "1234567890:test-bot-token"


def _make_init_data(payload: dict[str, str], token: str = BOT_TOKEN) -> str:
    """Build a properly-signed initData string for tests."""
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(payload.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode({**payload, "hash": digest})


def test_valid_init_data_returns_user_dict() -> None:
    user = {"id": 42, "first_name": "Ada"}
    init = _make_init_data({"user": json.dumps(user), "auth_date": "1700000000"})
    assert validate_init_data(init, BOT_TOKEN) == user


def test_missing_hash_raises_authentication_error() -> None:
    with pytest.raises(AuthenticationError):
        validate_init_data("user=%7B%22id%22%3A1%7D&auth_date=1", BOT_TOKEN)


def test_invalid_hash_raises_authentication_error() -> None:
    init = _make_init_data(
        {"user": json.dumps({"id": 1}), "auth_date": "1"}, token="other-token"
    )
    with pytest.raises(AuthenticationError):
        validate_init_data(init, BOT_TOKEN)


def test_missing_user_raises_validation_error() -> None:
    init = _make_init_data({"auth_date": "1700000000"})
    with pytest.raises(ValidationError):
        validate_init_data(init, BOT_TOKEN)


def test_invalid_user_json_raises_validation_error() -> None:
    init = _make_init_data({"user": "not-json", "auth_date": "1"})
    with pytest.raises(ValidationError):
        validate_init_data(init, BOT_TOKEN)


def test_empty_init_data_raises() -> None:
    with pytest.raises(AuthenticationError):
        validate_init_data("", BOT_TOKEN)


def test_empty_token_raises() -> None:
    with pytest.raises(AuthenticationError):
        validate_init_data("user=%7B%7D&hash=x", "")
