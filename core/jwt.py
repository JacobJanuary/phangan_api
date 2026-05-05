"""JWT helpers — pure functions, transport-agnostic.

Encoding lives here so the auth feature can issue tokens without depending
on the FastAPI security layer (which lives in `core.security`).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from core.exceptions import AuthenticationError


def create_access_token(
    *,
    payload: dict[str, Any],
    secret: str,
    algorithm: str,
    expires_minutes: int,
) -> str:
    """Encode a JWT access token with `exp` set to now+`expires_minutes`."""
    if not secret:
        raise ValueError("JWT secret must be non-empty")
    to_encode = dict(payload)
    to_encode["exp"] = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    return jwt.encode(to_encode, secret, algorithm=algorithm)


def decode_access_token(
    token: str, *, secret: str, algorithm: str
) -> dict[str, Any]:
    """Decode + verify a JWT. Raises `AuthenticationError` on any failure."""
    try:
        return jwt.decode(token, secret, algorithms=[algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Invalid authentication token") from exc
