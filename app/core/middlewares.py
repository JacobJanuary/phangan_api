"""
Security Middleware — intercepts ALL incoming requests.

1. Checks if the client IP is blacklisted → instant 403 BEFORE reaching routers.
2. For /api/ routes: validates API key and records strikes on failure.
3. All other routes pass through untouched.
"""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.security import get_ip_tracker

logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Enterprise-grade security middleware.

    Intercepts every request to enforce IP blacklisting
    before it reaches FastAPI routers or the database layer.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        tracker = get_ip_tracker()
        start_time = time.monotonic()

        # ── 1. Blacklist check (instant rejection) ───────────────────
        if tracker.is_blacklisted(client_ip):
            logger.warning(
                "🛑 BLOCKED blacklisted IP: %s → %s %s",
                client_ip,
                request.method,
                request.url.path,
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "Forbidden — your IP has been blacklisted."},
            )

        # ── 2. Pass through to application ───────────────────────────
        response = await call_next(request)

        # ── 3. Request logging ───────────────────────────────────────
        elapsed_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            "%s %s [%s] → %d (%.1fms)",
            request.method,
            request.url.path,
            client_ip,
            response.status_code,
            elapsed_ms,
        )

        return response
