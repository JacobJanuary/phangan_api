"""Lightweight in-process metrics.

Zero external dependencies. Exposes counters/gauges in Prometheus text
format at GET /metrics. For real production observability, replace with
prometheus_client or push to a real backend; this is a no-frills
introspection surface.

Usage:
    >>> from core.metrics import metrics, MetricsMiddleware
    >>> app.add_middleware(MetricsMiddleware)
    >>> # GET /metrics → text/plain Prometheus exposition
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from threading import Lock
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

logger = logging.getLogger(__name__)


class _Metrics:
    """Process-local counters. Thread-safe (Lock) for sync paths;
    asyncio is single-threaded so the lock is mostly cosmetic but cheap."""

    def __init__(self) -> None:
        self._lock = Lock()
        # http_requests_total{method, path, status}
        self._http_requests: dict[tuple[str, str, int], int] = defaultdict(int)
        # http_request_duration_seconds_sum{method, path}
        self._http_duration_sum: dict[tuple[str, str], float] = defaultdict(float)
        self._http_duration_count: dict[tuple[str, str], int] = defaultdict(int)
        self._started_at = time.time()

    def observe_http(
        self, method: str, path: str, status: int, duration_s: float
    ) -> None:
        key3 = (method, path, status)
        key2 = (method, path)
        with self._lock:
            self._http_requests[key3] += 1
            self._http_duration_sum[key2] += duration_s
            self._http_duration_count[key2] += 1

    def render(self) -> str:
        with self._lock:
            req = dict(self._http_requests)
            dsum = dict(self._http_duration_sum)
            dcount = dict(self._http_duration_count)
            uptime = time.time() - self._started_at

        lines: list[str] = []
        lines.append("# HELP phangan_uptime_seconds Process uptime in seconds.")
        lines.append("# TYPE phangan_uptime_seconds gauge")
        lines.append(f"phangan_uptime_seconds {uptime:.3f}")

        lines.append("# HELP phangan_http_requests_total HTTP request count.")
        lines.append("# TYPE phangan_http_requests_total counter")
        for (method, path, status), n in sorted(req.items()):
            lines.append(
                f'phangan_http_requests_total{{method="{method}",'
                f'path="{path}",status="{status}"}} {n}'
            )

        lines.append(
            "# HELP phangan_http_request_duration_seconds_sum "
            "Sum of request durations in seconds."
        )
        lines.append("# TYPE phangan_http_request_duration_seconds_sum counter")
        for (method, path), s in sorted(dsum.items()):
            lines.append(
                f'phangan_http_request_duration_seconds_sum'
                f'{{method="{method}",path="{path}"}} {s:.6f}'
            )

        lines.append(
            "# HELP phangan_http_request_duration_seconds_count "
            "Number of timed requests."
        )
        lines.append("# TYPE phangan_http_request_duration_seconds_count counter")
        for (method, path), n in sorted(dcount.items()):
            lines.append(
                f'phangan_http_request_duration_seconds_count'
                f'{{method="{method}",path="{path}"}} {n}'
            )

        lines.append("")  # trailing newline
        return "\n".join(lines)


metrics = _Metrics()


def _route_template(request: Request) -> str:
    """Use the matched route's path template (no high-cardinality
    explosion from path params like /events/{event_id})."""
    route = request.scope.get("route")
    if route is not None and hasattr(route, "path"):
        return route.path
    return request.url.path


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record per-request counters & latency."""

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        # Skip metrics endpoint itself to avoid recursive counts.
        if request.url.path == "/metrics":
            return await call_next(request)

        start = time.perf_counter()
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        except Exception:
            status = 500
            raise
        finally:
            duration = time.perf_counter() - start
            metrics.observe_http(
                request.method, _route_template(request), status, duration
            )


async def metrics_endpoint() -> PlainTextResponse:
    """GET /metrics → Prometheus text exposition."""
    return PlainTextResponse(
        metrics.render(), media_type="text/plain; version=0.0.4"
    )
