from __future__ import annotations

import pytest
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from sibyl_core.ai.errors import LLMProviderError
from sibyl_core.ai.llm import Generator


@pytest.mark.asyncio
async def test_generator_returns_text() -> None:
    generator = Generator(agent=Agent(TestModel(custom_output_text="hello Sibyl")))

    result = await generator.generate("say hi")

    assert result == "hello Sibyl"


@pytest.mark.asyncio
async def test_generator_streams_text_deltas() -> None:
    generator = Generator(agent=Agent(TestModel(custom_output_text="hello Sibyl")))

    chunks = [chunk async for chunk in generator.stream("say hi")]

    assert "".join(chunks) == "hello Sibyl"
    assert len(chunks) >= 1


@pytest.mark.asyncio
async def test_generator_passes_per_call_max_tokens() -> None:
    async def capture_settings(_: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        assert info.model_settings == {"max_tokens": 17}
        return ModelResponse(parts=[TextPart("ok")], model_name="function")

    generator = Generator(agent=Agent(FunctionModel(capture_settings)))

    result = await generator.generate("say hi", max_tokens=17)

    assert result == "ok"


@pytest.mark.asyncio
async def test_generator_maps_provider_failure() -> None:
    async def fail(_: list[ModelMessage], __: AgentInfo) -> ModelResponse:
        raise ModelHTTPError(500, "test-model", {"error": "boom"})

    generator = Generator(agent=Agent(FunctionModel(fail)))

    with pytest.raises(LLMProviderError):
        await generator.generate("say hi")
