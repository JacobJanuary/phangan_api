"""
Domain exception hierarchy.

Business-logic code raises these instead of returning sentinel values
or `None`. The interface layer (`error_handlers.py`) maps them to
HTTP responses; tests assert on the type, not on string contents.

Rules:

- All domain errors inherit from `DomainError`.
- Each subclass carries a stable `code` attribute used in the API
  response body, so frontends can branch on it.
- `details` is a dict of structured context that goes into logs (and
  into the response when the error is safe to expose).
- Never raise generic `Exception` from application code; if no
  category fits, add a new subclass here.
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base class for all errors originating in the domain or
    application layer."""

    code: str = "domain_error"
    http_status: int = 400

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_payload(self) -> dict[str, Any]:
        """Serializable representation for API responses."""
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


# ── 4xx — client errors ──────────────────────────────────────────────


class ValidationError(DomainError):
    """Input failed business-rule validation (not Pydantic validation,
    which produces 422 automatically)."""

    code = "validation_error"
    http_status = 400


class NotFoundError(DomainError):
    """A requested entity does not exist."""

    code = "not_found"
    http_status = 404


class AuthenticationError(DomainError):
    """Caller is not authenticated (missing or invalid token)."""

    code = "authentication_error"
    http_status = 401


class AuthorizationError(DomainError):
    """Caller is authenticated but not allowed to perform the action."""

    code = "authorization_error"
    http_status = 403


class ConflictError(DomainError):
    """Operation conflicts with the current state (e.g. duplicate
    resource, optimistic-lock failure)."""

    code = "conflict"
    http_status = 409


class RateLimitError(DomainError):
    """Caller exceeded a rate-limit threshold."""

    code = "rate_limited"
    http_status = 429


# ── 5xx — server / dependency errors ─────────────────────────────────


class ExternalServiceError(DomainError):
    """An upstream dependency (Telegram, AI provider, Mapbox) failed
    in a way that prevents completing the request."""

    code = "external_service_error"
    http_status = 502


class ConfigurationError(DomainError):
    """The service is misconfigured (missing required env var, etc.).
    Indicates an operational problem, not a user error."""

    code = "configuration_error"
    http_status = 500
