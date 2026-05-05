"""
FastAPI exception handlers that map domain errors to HTTP responses.

Registered once in the application factory. Keeps HTTP-specific
serialization concerns out of the application layer — use cases
raise `DomainError`, the framework handles the rest.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.exceptions import DomainError

logger = logging.getLogger(__name__)


def _build_response(error: DomainError, request: Request) -> JSONResponse:
    """Construct the JSON body and log the failure with context."""
    payload: dict[str, Any] = error.to_payload()

    logger.warning(
        "domain error: %s",
        error.code,
        extra={
            "error_code": error.code,
            "error_message": error.message,
            "error_details": error.details,
            "http_status": error.http_status,
            "method": request.method,
            "path": request.url.path,
        },
    )

    return JSONResponse(status_code=error.http_status, content=payload)


def register_error_handlers(app: FastAPI) -> None:
    """Attach the global domain-error handler to the FastAPI app.

    Call this exactly once during application bootstrap, after the
    `FastAPI` instance is created and before mounting routers.
    """

    @app.exception_handler(DomainError)
    async def _handle_domain_error(  # noqa: ANN202 — FastAPI signature
        request: Request, exc: DomainError
    ):
        return _build_response(exc, request)
