from __future__ import annotations

import pytest
from pydantic import SecretStr
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from sibyl_core.ai import validation
from sibyl_core.ai.llm.config import (
    ConfigField,
    LLMConfig,
    LLMSurface,
    ResolvedLLMConfig,
)


class StaticConfigSource:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    async def resolve(self, surface: LLMSurface) -> ResolvedLLMConfig:
        return ResolvedLLMConfig(
            surface=surface,
            provider=ConfigField(value=self.config.provider, source="db"),
            model=ConfigField(value=self.config.model, source="db"),
            temperature=ConfigField(value=self.config.temperature, source="db"),
            max_tokens=ConfigField(value=self.config.max_tokens, source="db"),
            timeout_seconds=ConfigField(value=self.config.timeout_seconds, source="db"),
            api_key=ConfigField(value=self.config.api_key, source="db"),
        )

    async def invalidate(self, surface: LLMSurface | None = None) -> None:
        return None


@pytest.mark.asyncio
async def test_check_provider_key_returns_valid_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        validation,
        "build_model",
        lambda config: TestModel(custom_output_text="ok", model_name=config.model),
    )

    result = await validation.check_provider_key("openai", "key")

    assert result.valid is True
    assert result.status == "valid"
    assert result.model == "gpt-5.4-nano"
    assert result.output_tokens is not None


@pytest.mark.asyncio
async def test_check_model_availability_classifies_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail(_: list[ModelMessage], __: AgentInfo) -> ModelResponse:
        raise ModelHTTPError(404, "missing-model", {"error": "missing"})

    monkeypatch.setattr(validation, "build_model", lambda _: FunctionModel(fail))

    result = await validation.check_model_availability("gemini", "missing-model", "key")

    assert result.valid is False
    assert result.status == "model_not_found"
    assert result.requested_model == "missing-model"


@pytest.mark.asyncio
async def test_surface_config_returns_parsed_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        validation,
        "build_model",
        lambda _: TestModel(custom_output_args={"ok": True, "summary": "ready"}),
    )
    source = StaticConfigSource(
        LLMConfig(
            provider="anthropic",
            model="claude-haiku-4-5",
            api_key=SecretStr("anthropic-key"),
        )
    )

    result = await validation.test_surface_config(LLMSurface.CRAWLER, source)

    assert result.valid is True
    assert result.status == "valid"
    assert result.parsed_output == {"ok": True, "summary": "ready"}
    assert result.model == "claude-haiku-4-5-20251001"


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (401, "invalid_key"),
        (403, "permission_denied"),
        (404, "model_not_found"),
        (429, "rate_limited"),
        (500, "network"),
    ],
)
def test_status_for_http_code(status_code: int, expected: str) -> None:
    assert validation._status_for_http_code(status_code) == expected
