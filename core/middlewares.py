"""Security middleware — IP blacklist enforcement + access logging."""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from core.security import get_ip_tracker

logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Block blacklisted IPs and emit a one-line request log."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        tracker = get_ip_tracker()
        start_time = time.monotonic()

        if tracker.is_blacklisted(client_ip):
            logger.warning(
                "Blocked blacklisted IP",
                extra={
                    "ip": client_ip,
                    "method": request.method,
                    "path": request.url.path,
                },
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "Forbidden — your IP has been blacklisted."},
            )

        response = await call_next(request)

        elapsed_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            "%s %s [%s] -> %d (%.1fms)",
            request.method,
            request.url.path,
            client_ip,
            response.status_code,
            elapsed_ms,
        )
        return response
