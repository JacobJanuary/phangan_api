"""FastAPI dependency providers shared across features.

These wire together the transport layer (FastAPI) with the core domain.
Concrete dependencies (DB pool, JWT settings) come from the composition
root via `request.app.state` to avoid import-time globals.
"""

from __future__ import annotations

import asyncpg
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import Settings
from core.exceptions import AuthenticationError
from core.jwt import decode_access_token

_security = HTTPBearer(auto_error=True)


def get_settings_dep(request: Request) -> Settings:
    """Return the `Settings` instance attached at app startup."""
    settings: Settings | None = getattr(request.app.state, "settings", None)
    if settings is None:
        raise RuntimeError("Settings missing on app.state — check composition root")
    return settings


def get_pool_dep(request: Request) -> asyncpg.Pool:
    """Return the asyncpg pool attached at app startup."""
    pool: asyncpg.Pool | None = getattr(request.app.state, "pool", None)
    if pool is None:
        raise RuntimeError("DB pool missing on app.state — check composition root")
    return pool


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
    settings: Settings = Depends(get_settings_dep),
) -> int:
    """Decode the Bearer JWT and return the internal user id (`sub`)."""
    payload = decode_access_token(
        credentials.credentials,
        secret=settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AuthenticationError("Token is missing subject (user ID)")
    try:
        return int(user_id_str)
    except (TypeError, ValueError) as exc:
        raise AuthenticationError("Token subject is not a valid user id") from exc
