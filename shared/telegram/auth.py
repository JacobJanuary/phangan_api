"""Pure (transport-agnostic) Telegram WebApp initData validation.

This module deliberately raises domain exceptions (`AuthenticationError`,
`ValidationError`) instead of `HTTPException`. Translation to HTTP responses
happens in `core.error_handlers`.

Reference: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.parse
from typing import Any

from core.exceptions import AuthenticationError, ValidationError


_MAX_INIT_DATA_AGE_SECONDS = int(os.getenv("TG_INIT_DATA_MAX_AGE_SECONDS", "600"))
_MAX_INIT_DATA_CLOCK_SKEW_SECONDS = 60


def validate_init_data(init_data: str, bot_token: str) -> dict[str, Any]:
    """Validate the HMAC signature of a Telegram initData string.

    Args:
        init_data: Raw query string sent by the Mini App.
        bot_token: Telegram bot token used to derive the secret key.

    Returns:
        Parsed `user` JSON object on success.

    Raises:
        AuthenticationError: signature is missing or invalid.
        ValidationError: `user` field is missing or not valid JSON.
    """
    if not init_data:
        raise AuthenticationError("Empty initData")
    if not bot_token:
        raise AuthenticationError("Bot token is not configured")

    parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise AuthenticationError("Missing 'hash' in initData")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))

    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    calculated_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise AuthenticationError("Invalid Telegram signature")

    auth_date_raw = parsed.get("auth_date")
    if not auth_date_raw:
        raise AuthenticationError("Missing auth_date in initData")
    try:
        auth_date = int(auth_date_raw)
    except (TypeError, ValueError) as exc:
        raise AuthenticationError("Invalid auth_date in initData") from exc

    now = int(time.time())
    if auth_date > now + _MAX_INIT_DATA_CLOCK_SKEW_SECONDS:
        raise AuthenticationError("Telegram initData auth_date is in the future")
    if now - auth_date > _MAX_INIT_DATA_AGE_SECONDS:
        raise AuthenticationError("Telegram initData has expired")

    user_str = parsed.get("user")
    if not user_str:
        raise ValidationError("User data missing from initData")

    try:
        user_data = json.loads(user_str)
    except json.JSONDecodeError as exc:
        raise ValidationError("Invalid user JSON in initData") from exc

    if not isinstance(user_data, dict):
        raise ValidationError("Telegram user payload must be an object")

    return user_data
