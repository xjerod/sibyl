"""Shared AI substrate exceptions."""

from __future__ import annotations

from typing import Any

from pydantic_ai.exceptions import ModelHTTPError, ModelRetry, UnexpectedModelBehavior

from sibyl_core.errors import SibylError


class AIError(SibylError):
    """Base exception for AI substrate failures."""


class LLMError(AIError):
    """Base exception for language model failures."""

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        surface: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details: dict[str, Any] = details.copy() if details else {}
        if provider is not None:
            merged_details["provider"] = provider
        if model is not None:
            merged_details["model"] = model
        if surface is not None:
            merged_details["surface"] = surface
        super().__init__(message, details=merged_details)
        self.provider = provider
        self.model = model
        self.surface = surface


class LLMConfigError(LLMError):
    """Raised when LLM configuration cannot be resolved."""


class LLMValidationError(LLMError):
    """Raised when provider output cannot satisfy a requested schema."""


class LLMRateLimitError(LLMError):
    """Raised when a provider rate limit is hit."""


class LLMProviderError(LLMError):
    """Raised when a provider rejects or fails a request."""


class LLMTimeoutError(LLMError):
    """Raised when a provider request times out."""


def classify_llm_exception(
    exc: Exception,
    *,
    provider: str | None = None,
    model: str | None = None,
    surface: str | None = None,
) -> LLMError:
    """Map provider and PydanticAI failures into Sibyl's error taxonomy."""
    if isinstance(exc, LLMError):
        return exc

    if _is_timeout(exc):
        return LLMTimeoutError(
            "LLM provider request timed out",
            provider=provider,
            model=model,
            surface=surface,
            details={"cause": str(exc)},
        )

    if isinstance(exc, ModelHTTPError):
        details = {"status_code": exc.status_code, "body": exc.body}
        if exc.status_code == 429:
            return LLMRateLimitError(
                "LLM provider rate limit exceeded",
                provider=provider,
                model=exc.model_name or model,
                surface=surface,
                details=details,
            )
        return LLMProviderError(
            f"LLM provider request failed with HTTP {exc.status_code}",
            provider=provider,
            model=exc.model_name or model,
            surface=surface,
            details=details,
        )

    if isinstance(exc, (ModelRetry, UnexpectedModelBehavior)):
        return LLMValidationError(
            "LLM output could not be validated",
            provider=provider,
            model=model,
            surface=surface,
            details={"cause": str(exc)},
        )

    return LLMProviderError(
        "LLM provider request failed",
        provider=provider,
        model=model,
        surface=surface,
        details={"cause": str(exc), "exception_type": type(exc).__name__},
    )


def _is_timeout(exc: Exception) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    try:
        import httpx
    except ImportError:  # pragma: no cover - httpx is already a core dependency
        return False
    return isinstance(exc, httpx.TimeoutException)
