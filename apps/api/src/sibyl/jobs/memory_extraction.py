"""Queued LLM extraction for prose-bearing memory sources."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import structlog

from sibyl.config import settings
from sibyl.jobs.queue import get_queue
from sibyl_core.ai.errors import LLMError
from sibyl_core.ai.memory_extraction import (
    build_memory_entity_extraction_prompt,
    memory_entity_extractor,
)
from sibyl_core.models.memory_extraction import MemoryEntityExtractionResult
from sibyl_core.observability import elapsed_ms, telemetry_registry

log = structlog.get_logger()

_PROJECTABLE_MEMORY_TYPES = frozenset({"episode", "session"})


@dataclass(frozen=True, slots=True)
class MemoryExtractionEnqueueResult:
    status: str
    job_ids: tuple[str, ...] = ()
    queued_sources: int = 0
    skipped_sources: int = 0
    queue_depth: int | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class _SourcePayload:
    source: dict[str, Any]
    source_id: str
    char_count: int


async def enqueue_memory_extraction_batches(
    sources_data: list[dict[str, Any]],
    group_id: str,
    *,
    created_source_ids: list[str] | None = None,
) -> MemoryExtractionEnqueueResult:
    """Queue bounded memory extraction jobs when the feature flag allows it."""
    if not settings.auto_extract_entities:
        telemetry_registry().record_memory_extraction_enqueue(
            status="skipped",
            sources=len(sources_data),
        )
        return MemoryExtractionEnqueueResult(
            status="skipped",
            skipped_sources=len(sources_data),
            reason="disabled",
        )

    queue = get_queue()
    health = await queue.health()
    queue_depth = _int_value(health.get("queue_depth"))
    if queue_depth >= settings.memory_extraction_max_queue_depth:
        telemetry_registry().record_memory_extraction_enqueue(
            status="backpressure",
            sources=len(sources_data),
            queue_depth=queue_depth,
        )
        return MemoryExtractionEnqueueResult(
            status="backpressure",
            skipped_sources=len(sources_data),
            queue_depth=queue_depth,
            reason="queue_depth",
        )

    source_payloads = _source_payloads(
        sources_data,
        created_source_ids=created_source_ids,
        max_source_chars=settings.memory_extraction_max_source_chars,
    )
    batches = _batch_source_payloads(
        source_payloads,
        max_sources=settings.memory_extraction_max_sources_per_job,
        max_chars=settings.memory_extraction_max_job_chars,
    )
    if not batches:
        telemetry_registry().record_memory_extraction_enqueue(
            status="skipped",
            sources=len(sources_data),
            queue_depth=queue_depth,
        )
        return MemoryExtractionEnqueueResult(
            status="skipped",
            skipped_sources=len(sources_data),
            queue_depth=queue_depth,
            reason="no_projectable_sources",
        )

    available_slots = settings.memory_extraction_max_queue_depth - queue_depth
    batches_to_enqueue = batches[:available_slots]
    skipped_sources = len(source_payloads) - sum(len(batch) for batch in batches_to_enqueue)
    job_ids: list[str] = []
    for batch in batches_to_enqueue:
        job_id = await queue.enqueue_memory_extraction(
            [item.source for item in batch],
            group_id,
            created_source_ids=[item.source_id for item in batch],
            max_entities_per_source=settings.memory_extraction_max_entities_per_source,
            max_source_chars=settings.memory_extraction_max_source_chars,
            max_concurrent=settings.memory_extraction_max_concurrency,
            max_tokens=settings.memory_extraction_max_tokens,
        )
        job_ids.append(job_id)

    status = "queued" if job_ids else "backpressure"
    telemetry_registry().record_memory_extraction_enqueue(
        status=status,
        sources=sum(len(batch) for batch in batches_to_enqueue),
        batches=len(job_ids),
        queue_depth=queue_depth,
    )
    return MemoryExtractionEnqueueResult(
        status=status,
        job_ids=tuple(job_ids),
        queued_sources=sum(len(batch) for batch in batches_to_enqueue),
        skipped_sources=skipped_sources,
        queue_depth=queue_depth,
        reason=None if job_ids else "queue_depth",
    )


async def extract_memory_entities(
    ctx: dict[str, Any],  # noqa: ARG001
    sources_data: list[dict[str, Any]],
    group_id: str,
    *,
    created_source_ids: list[str] | None = None,
    max_entities_per_source: int = 8,
    max_source_chars: int = 12_000,
    max_concurrent: int = 2,
    max_tokens: int = 2048,
) -> dict[str, Any]:
    """Run bounded LLM entity extraction for memory source prose."""
    started_at = time.perf_counter()
    source_payloads = _source_payloads(
        sources_data,
        created_source_ids=created_source_ids,
        max_source_chars=max_source_chars,
    )
    prompts = [
        build_memory_entity_extraction_prompt(
            title=str(source.source.get("name") or source.source_id),
            content=str(source.source.get("content") or ""),
            source_type=str(source.source.get("entity_type") or "memory"),
            max_entities=max_entities_per_source,
        )
        for source in source_payloads
    ]
    estimated_input_tokens = sum(_estimate_tokens(prompt) for prompt in prompts)
    extractor = memory_entity_extractor(max_tokens=max_tokens)

    errors: list[dict[str, str]] = []
    extractions: list[dict[str, Any]] = []
    extracted_entities = 0
    results = await extractor.extract_many(prompts, max_concurrent=max_concurrent)
    for source, result in zip(source_payloads, results, strict=True):
        if isinstance(result, LLMError):
            errors.append(
                {
                    "source_id": source.source_id,
                    "error_type": type(result).__name__,
                    "message": str(result),
                }
            )
            continue
        entities = [
            entity.model_dump(mode="json") for entity in _limited_entities(result, max_entities_per_source)
        ]
        extractions.append({"source_id": source.source_id, "entities": entities})
        extracted_entities += len(entities)

    status = "ok" if not errors else "partial" if extractions else "error"
    duration_ms = elapsed_ms(started_at)
    telemetry_registry().record_memory_extraction_run(
        status=status,
        duration_ms=duration_ms,
        sources=len(source_payloads),
        extracted_entities=extracted_entities,
        estimated_input_tokens=estimated_input_tokens,
    )
    result = {
        "group_id": group_id,
        "sources": len(source_payloads),
        "extracted_entities": extracted_entities,
        "estimated_input_tokens": estimated_input_tokens,
        "errors": errors,
        "extractions": extractions,
    }
    if errors:
        log.warning("memory_extraction_complete", status=status, **result)
    else:
        log.info("memory_extraction_complete", status=status, **result)
    return result


def _source_payloads(
    sources_data: list[dict[str, Any]],
    *,
    created_source_ids: list[str] | None,
    max_source_chars: int,
) -> list[_SourcePayload]:
    payloads: list[_SourcePayload] = []
    for index, source in enumerate(sources_data):
        entity_type = str(source.get("entity_type") or "").lower()
        if entity_type not in _PROJECTABLE_MEMORY_TYPES:
            continue
        content = str(source.get("content") or source.get("description") or "").strip()
        if not content:
            continue
        trimmed_content = content[:max_source_chars]
        source_id = (
            created_source_ids[index]
            if created_source_ids is not None and index < len(created_source_ids)
            else str(source.get("id") or "")
        )
        payload = {**source, "content": trimmed_content}
        payloads.append(
            _SourcePayload(
                source=payload,
                source_id=source_id,
                char_count=len(trimmed_content),
            )
        )
    return payloads


def _batch_source_payloads(
    payloads: list[_SourcePayload],
    *,
    max_sources: int,
    max_chars: int,
) -> list[list[_SourcePayload]]:
    batches: list[list[_SourcePayload]] = []
    current: list[_SourcePayload] = []
    current_chars = 0
    for payload in payloads:
        would_exceed_sources = len(current) >= max_sources
        would_exceed_chars = current_chars + payload.char_count > max_chars
        if current and (would_exceed_sources or would_exceed_chars):
            batches.append(current)
            current = []
            current_chars = 0
        current.append(payload)
        current_chars += payload.char_count
    if current:
        batches.append(current)
    return batches


def _limited_entities(
    result: MemoryEntityExtractionResult,
    max_entities: int,
) -> list[Any]:
    return result.entities[:max(1, max_entities)]


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _int_value(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


__all__ = [
    "MemoryExtractionEnqueueResult",
    "enqueue_memory_extraction_batches",
    "extract_memory_entities",
]
