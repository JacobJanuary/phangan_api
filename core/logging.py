"""
Structured logging configuration with request correlation.

Every request gets a `request_id` (UUID4) attached to a `ContextVar`.
The logging filter copies it onto every log record produced during
the request's lifetime, so log aggregators can group records by
request without parsing prose messages.

Two output formats are supported via the `LOG_FORMAT` setting:

- `json`: one JSON object per line, suitable for log shippers.
- `text`: human-readable, useful in development.

Usage:

    >>> from core.logging import configure_logging, RequestContextMiddleware
    >>> configure_logging(level="INFO", format="json")
    >>> app.add_middleware(RequestContextMiddleware)
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextvars import ContextVar
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

# Request-scoped correlation id. Set by RequestContextMiddleware.
_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    """Return the request id of the current task, or None if outside
    a request context (e.g. background workers, startup)."""
    return _request_id_var.get()


# ── Filter / formatter ──────────────────────────────────────────────


class _RequestContextFilter(logging.Filter):
    """Inject the current request_id into every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_var.get() or "-"
        return True


_RESERVED_LOG_RECORD_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname",
    "filename", "module", "exc_info", "exc_text", "stack_info",
    "lineno", "funcName", "created", "msecs", "relativeCreated",
    "thread", "threadName", "processName", "process", "getMessage",
    "request_id", "message",
}


class _JsonFormatter(logging.Formatter):
    """Format records as a single-line JSON document."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "time": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        # Include any structured `extra={...}` keys passed by callers.
        for key, value in record.__dict__.items():
            if key in _RESERVED_LOG_RECORD_ATTRS or key.startswith("_"):
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except (TypeError, ValueError):
                payload[key] = repr(value)

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


class _TextFormatter(logging.Formatter):
    """Human-readable format with request_id."""

    DEFAULT_FORMAT = (
        "%(asctime)s [%(levelname)s] [%(request_id)s] "
        "%(name)s — %(message)s"
    )

    def __init__(self) -> None:
        super().__init__(fmt=self.DEFAULT_FORMAT)


# ── Public API ──────────────────────────────────────────────────────


def configure_logging(*, level: str = "INFO", format: str = "json") -> None:
    """
    Reset the root logger and attach our handler.

    Safe to call multiple times — existing handlers are removed first.
    """
    if format == "json":
        formatter: logging.Formatter = _JsonFormatter()
    elif format == "text":
        formatter = _TextFormatter()
    else:
        raise ValueError(f"Unsupported log format: {format!r}")

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(_RequestContextFilter())

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level.upper())

    # Quiet down noisy loggers from third parties.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


# ── Middleware ──────────────────────────────────────────────────────


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Attach a request_id to every incoming request.

    If the client supplies an `X-Request-ID` header it is reused
    (useful for end-to-end tracing across services); otherwise we
    generate a UUID4. The id is logged once on completion alongside
    method, path, status and elapsed time, and propagated back to the
    client in the response header.
    """

    HEADER_NAME = "X-Request-ID"

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._logger = logging.getLogger("phangan.access")

    async def dispatch(  # noqa: D401 — Starlette signature
        self, request: Request, call_next
    ) -> Response:
        request_id = request.headers.get(self.HEADER_NAME) or str(uuid.uuid4())
        token = _request_id_var.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            _request_id_var.reset(token)

        response.headers[self.HEADER_NAME] = request_id

        self._logger.info(
            "request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "elapsed_ms": round(elapsed_ms, 2),
                "client_ip": request.client.host if request.client else None,
            },
        )
        return response
