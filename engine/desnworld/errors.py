"""
Structured error types for the DESNWORLD engine.

Every failure mode surfaced to callers is one of these types so the CLI, the
local dev server, and the GitHub Actions workflow can report actionable
messages instead of raw stack traces.
"""

from __future__ import annotations

from typing import List, Optional


class EngineError(Exception):
    """Base class for DESNWORLD engine failures."""

    #: Short machine-readable code used by the CLI/server error payloads.
    code = "engine_error"

    def __init__(self, message: str, *, hint: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.hint = hint

    def to_payload(self) -> dict:
        payload = {"error": self.code, "message": self.message}
        if self.hint:
            payload["hint"] = self.hint
        return payload


class InputValidationError(EngineError):
    """The user's scenario request failed validation."""

    code = "input_validation_error"

    def __init__(self, message: str, *, problems: Optional[List[str]] = None, hint: Optional[str] = None):
        super().__init__(message, hint=hint)
        self.problems = problems or []

    def to_payload(self) -> dict:
        payload = super().to_payload()
        if self.problems:
            payload["problems"] = self.problems
        return payload


class MissingCredentialsError(EngineError):
    """No AI provider credentials are configured."""

    code = "missing_credentials"


class ProviderError(EngineError):
    """The AI provider rejected or failed a request."""

    code = "provider_error"


class RateLimitError(ProviderError):
    """The AI provider rate-limited the request after retries were exhausted."""

    code = "rate_limit_error"


class ProviderTimeoutError(ProviderError):
    """The AI provider request timed out."""

    code = "provider_timeout"


class MalformedResponseError(ProviderError):
    """The AI provider returned content that is not usable JSON."""

    code = "malformed_response"

    def __init__(
        self,
        message: str,
        *,
        finish_reason: Optional[str] = None,
        hint: Optional[str] = None,
    ):
        super().__init__(message, hint=hint)
        self.finish_reason = finish_reason


class SchemaValidationError(EngineError):
    """Model output failed the DESNWORLD scenario-report schema."""

    code = "schema_validation_error"

    def __init__(self, message: str, *, problems: Optional[List[str]] = None, hint: Optional[str] = None):
        super().__init__(message, hint=hint)
        self.problems = problems or []

    def to_payload(self) -> dict:
        payload = super().to_payload()
        if self.problems:
            payload["problems"] = payload.get("problems", []) + self.problems
        return payload
