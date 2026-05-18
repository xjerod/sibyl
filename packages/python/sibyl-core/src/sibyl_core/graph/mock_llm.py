"""Mock LLM client for testing without API keys.

This module provides a mock LLM client that returns valid but empty responses,
allowing graph workflows to run without actual LLM calls.

Usage:
    Set SIBYL_MOCK_LLM=true to enable mock mode in tests/CI.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import structlog
from pydantic import BaseModel

log = structlog.get_logger()


@dataclass(frozen=True)
class MockLLMConfig:
    api_key: str = "mock-key"
    model: str = "mock-model"
    small_model: str = "mock-small-model"


class MockLLMClient:
    """Mock LLM client that returns empty extraction results.

    Used for:
    - CI/CD testing without API keys
    - Local development/debugging
    - Integration tests
    """

    def __init__(self) -> None:
        """Initialize mock client with minimal config."""
        self.config = MockLLMConfig()
        self.model = self.config.model
        self.small_model = self.config.small_model
        self.token_tracker = SimpleNamespace()
        self.tracer: object | None = None

    def set_tracer(self, tracer: object) -> None:
        self.tracer = tracer

    async def generate_response(
        self,
        messages: list[Any],
        response_model: type[BaseModel] | None = None,
        max_tokens: int | None = None,
        model_size: Any | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        return await self._generate_response(
            messages,
            response_model=response_model,
            max_tokens=max_tokens or 1000,
            model_size=model_size,
        )

    async def _generate_response(
        self,
        messages: list[Any],
        response_model: type[BaseModel] | None = None,
        max_tokens: int = 1000,
        model_size: Any | None = None,
    ) -> dict[str, Any]:
        """Return mock response matching expected schema.

        Returns empty/default responses without making actual LLM API calls.

        Args:
            messages: Chat messages (ignored in mock)
            response_model: Pydantic model for structured output
            max_tokens: Token limit (ignored)
            model_size: Model size preference (ignored)

        Returns:
            Dict matching response_model schema with empty/default values
        """
        model_name = response_model.__name__ if response_model else "unknown"
        log.debug("Mock LLM called", response_model=model_name)

        # Return appropriate empty response based on response model
        if response_model is None:
            return {"content": ""}

        # Handle Graphiti's extraction models by returning empty lists
        # This allows the workflow to complete without extracting entities/edges
        response = self._create_empty_response(response_model)

        log.debug("Mock LLM response", model=model_name, response=response)
        return response

    def _create_empty_response(self, response_model: type[BaseModel]) -> dict[str, Any]:
        """Create an empty/default response for a Pydantic model.

        Inspects model fields and returns appropriate empty values:
        - Lists -> []
        - Strings -> ""
        - Booleans -> False
        - Optional -> None

        Args:
            response_model: Pydantic model class

        Returns:
            Dict with empty/default values for all fields
        """
        result: dict[str, Any] = {}

        for field_name, field_info in response_model.model_fields.items():
            annotation = field_info.annotation

            # Get the origin type (List, Optional, etc.)
            origin = getattr(annotation, "__origin__", None)

            if origin is list:
                result[field_name] = []
            elif annotation is str:
                result[field_name] = ""
            elif annotation is bool:
                result[field_name] = False
            elif annotation is int:
                result[field_name] = 0
            elif annotation is float:
                result[field_name] = 0.0
            else:
                # For Optional types and complex types, use None
                result[field_name] = None

        return result
