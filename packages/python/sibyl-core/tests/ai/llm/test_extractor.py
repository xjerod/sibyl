from __future__ import annotations

import pytest
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from sibyl_core.ai.errors import LLMProviderError, LLMRateLimitError, LLMValidationError
from sibyl_core.ai.llm import Extractor


class Payload(BaseModel):
    name: str
    score: float


@pytest.mark.asyncio
async def test_extractor_returns_parsed_model() -> None:
    agent = Agent(TestModel(custom_output_args={"name": "Sibyl", "score": 0.9}), output_type=Payload)
    extractor = Extractor(Payload, agent=agent)

    result = await extractor.extract("extract")

    assert result == Payload(name="Sibyl", score=0.9)


@pytest.mark.asyncio
async def test_extractor_maps_validation_failure() -> None:
    agent = Agent(FunctionModel(_invalid_json_response), output_type=Payload, output_retries=0)
    extractor = Extractor(Payload, agent=agent, output_retries=0)

    with pytest.raises(LLMValidationError):
        await extractor.extract("extract")


@pytest.mark.asyncio
async def test_extractor_maps_rate_limit_failure() -> None:
    async def fail(_: list[ModelMessage], __: AgentInfo) -> ModelResponse:
        raise ModelHTTPError(429, "test-model", {"error": "slow down"})

    extractor = Extractor(Payload, agent=Agent(FunctionModel(fail), output_type=Payload))

    with pytest.raises(LLMRateLimitError):
        await extractor.extract("extract")


@pytest.mark.asyncio
async def test_extract_many_returns_partial_errors() -> None:
    extractor = Extractor(Payload, agent=Agent(FunctionModel(_prompt_sensitive_response), output_type=Payload))

    results = await extractor.extract_many(["good", "bad"], max_concurrent=2)

    assert results[0] == Payload(name="good", score=1.0)
    assert isinstance(results[1], LLMProviderError)


async def _invalid_json_response(_: list[ModelMessage], __: AgentInfo) -> ModelResponse:
    return ModelResponse(parts=[TextPart("not json")], model_name="function")


async def _prompt_sensitive_response(
    messages: list[ModelMessage],
    info: AgentInfo,
) -> ModelResponse:
    prompt = _last_user_prompt(messages)
    if "bad" in prompt:
        raise ModelHTTPError(500, "test-model", {"error": "boom"})

    output_tool = info.output_tools[0]
    return ModelResponse(
        parts=[ToolCallPart(output_tool.name, {"name": prompt, "score": 1.0})],
        model_name="function",
    )


def _last_user_prompt(messages: list[ModelMessage]) -> str:
    for message in reversed(messages):
        if not isinstance(message, ModelRequest):
            continue
        for part in reversed(message.parts):
            content = getattr(part, "content", None)
            if isinstance(content, str):
                return content
    return ""
