"""Text generation helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any

from pydantic_ai import Agent

from sibyl_core.ai.clients import get_agent
from sibyl_core.ai.errors import LLMError, classify_llm_exception
from sibyl_core.ai.llm.config import LLMSurface


class Generator:
    def __init__(
        self,
        *,
        surface: LLMSurface = LLMSurface.DEFAULT,
        system_prompt: str | Sequence[str] | None = None,
        model_override: str | None = None,
        output_retries: int | None = 2,
        agent: Agent[Any, Any] | None = None,
    ) -> None:
        self.surface = surface
        self.system_prompt = system_prompt
        self.model_override = model_override
        self.output_retries = output_retries
        self._agent = agent

    async def generate(self, prompt: str) -> str:
        try:
            agent = await self._get_agent()
            result = await agent.run(prompt, output_type=str)
            return result.output
        except Exception as exc:
            raise self._classify(exc) from exc

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        try:
            agent = await self._get_agent()
            async with agent.run_stream(prompt, output_type=str) as stream:
                async for text in stream.stream_text(delta=True):
                    yield text
        except Exception as exc:
            raise self._classify(exc) from exc

    async def _get_agent(self) -> Agent[Any, Any]:
        if self._agent is not None:
            return self._agent
        return await get_agent(
            self.surface,
            output_type=str,
            system_prompt=self.system_prompt,
            model_override=self.model_override,
            output_retries=self.output_retries,
        )

    def _classify(self, exc: Exception) -> LLMError:
        return classify_llm_exception(
            exc,
            model=self.model_override,
            surface=self.surface.value,
        )
