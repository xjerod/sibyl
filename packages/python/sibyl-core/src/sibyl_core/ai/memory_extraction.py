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
Extract durable graph handles from Sibyl memory prose.

Return only entities that future retrieval can use as stable anchors.
Prefer specific tools, languages, named domains, reusable patterns, and procedures.
Skip throwaway wording, generic nouns, people names without durable technical context,
and anything not directly supported by the provided text.
Keep names short, canonical, and reusable across sessions.
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
