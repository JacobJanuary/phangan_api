"""
Telegram Mini App authentication logic.
Validates the cryptographic signature of the initData string.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import urllib.parse

from fastapi import HTTPException
from app.core.config import get_settings

import logging
logger = logging.getLogger(__name__)

def validate_telegram_data(init_data: str, bot_token: str | None = None) -> dict:
    """
    Validates Telegram WebApp initData string using HMAC-SHA256.
    See: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    
    Raises:
        HTTPException: if validation fails or user data is missing.
    
    Returns:
        dict: The parsed user JSON object.
    """
    if bot_token is None:
        settings = get_settings()
        bot_token = settings.BOT_TOKEN

    # Parse query string
    logger.error(f"DEBUG INITDATA RAW (len={len(init_data)}): {init_data}")
    # We must use standard parse_qsl to handle all URL-encoded characters (like %22 -> ")
    parsed_items = urllib.parse.parse_qsl(init_data, keep_blank_values=True)
    parsed_dict = dict(parsed_items)
    logger.error(f"DEBUG PARSED_DICT: {list(parsed_dict.keys())}")

    if "hash" not in parsed_dict:
        logger.error("Missing 'hash' in initData")
        raise HTTPException(status_code=403, detail="Invalid Telegram signature")
        
    received_hash = parsed_dict.pop("hash")
    
    # CRITICAL: Since Telegram API 7.0, 'signature' must also be EXCLUDED from the data-check-string
    parsed_dict.pop("signature", None)
    # Sort keys alphabetically and format data-check-string
    data_check_list = [f"{k}={v}" for k, v in sorted(parsed_dict.items())]
    data_check_string = "\n".join(data_check_list)
    
    # Generate secret key -> HMAC_SHA256("WebAppData", bot_token)
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode("utf-8"),
        digestmod=hashlib.sha256
    ).digest()
    
    # Calculate signature -> HMAC_SHA256(secret_key, data_check_string)
    calculated_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(calculated_hash, received_hash):
        logger.error(f"Telegram Auth Failed!")
        logger.error(f"Received Hash: {received_hash}")
        logger.error(f"Calculated Hash: {calculated_hash}")
        logger.error(f"Data Check String:\n{data_check_string}")
        logger.error(f"Bot Token Preview: {bot_token[:5]}***")
        raise HTTPException(status_code=403, detail="Invalid Telegram signature")
        
    user_str = parsed_dict.get("user")
    if not user_str:
        raise HTTPException(status_code=400, detail="User data missing from initData")
        
    try:
        user_data = json.loads(user_str)
        return user_data
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid user data format")
