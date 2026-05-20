"""LLM extraction helpers for turning prose memories into graph handles."""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent

from sibyl_core.ai.llm import Extractor, LLMSurface
from sibyl_core.models.memory_extraction import (
    MAX_MEMORY_EXTRACTED_ENTITIES,
    MemoryEntityExtractionResult,
    MemoryExtractionEntityType,
)

MEMORY_ENTITY_EXTRACTION_SYSTEM_PROMPT = """\
Extract durable graph handles and atomic memory claims from Sibyl memory prose.

Support both personal and technical memory. Future retrieval should be able to
find the original source through the entities you return.

Prefer answer-bearing facts and anchors: people and relationships, places,
objects, purchases, preferences, habits, limits, goals, dated events, tools,
languages, domains, reusable patterns, and procedures.

Use claim for concrete facts, preference for likes/dislikes/habits/limits,
person for named people, place for locations, event for dated activities or
milestones, artifact for objects/media/files/systems, and the technical types
when they are the most specific fit.

Keep names short and canonical, but preserve the answer-bearing detail: for
example, "Instagram screen time average", "coffee limit decreased",
"Air Fryer purchase", or "Rachel's birthday". Evidence should be a short source
span. Skip generic assistant advice unless it is tied to a user-specific fact.
"""

_ENTITY_TYPES = ", ".join(item.value for item in MemoryExtractionEntityType)


def build_memory_entity_extraction_prompt(
    *,
    title: str,
    content: str,
    source_type: str = "memory",
    max_entities: int = 8,
) -> str:
    bounded_max = max(1, min(max_entities, MAX_MEMORY_EXTRACTED_ENTITIES))
    return "\n\n".join(
        (
            f"Source type: {source_type.strip() or 'memory'}",
            f"Title: {title.strip() or 'Untitled memory'}",
            f"Allowed entity types: {_ENTITY_TYPES}",
            f"Extract up to {bounded_max} entities.",
            "Content:",
            content.strip(),
        )
    )


def memory_entity_extractor(
    *,
    agent: Agent[Any, Any] | None = None,
    model_override: str | None = None,
    max_tokens: int | None = 2048,
    output_retries: int | None = 2,
) -> Extractor[MemoryEntityExtractionResult]:
    return Extractor(
        MemoryEntityExtractionResult,
        surface=LLMSurface.MEMORY,
        system_prompt=MEMORY_ENTITY_EXTRACTION_SYSTEM_PROMPT,
        model_override=model_override,
        max_tokens=max_tokens,
        output_retries=output_retries,
        agent=agent,
    )


__all__ = [
    "MEMORY_ENTITY_EXTRACTION_SYSTEM_PROMPT",
    "build_memory_entity_extraction_prompt",
    "memory_entity_extractor",
]
