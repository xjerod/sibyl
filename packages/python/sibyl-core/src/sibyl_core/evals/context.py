"""Evaluation helpers for Sibyl context packs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sibyl_core.models.context import ContextFacet, ContextItem, ContextPack
from sibyl_core.tools.context import context_pack_to_markdown


@dataclass(frozen=True)
class ContextPackFixture:
    """Expected behavior for a context-pack dogfood fixture."""

    name: str
    required_item_ids: set[str] = field(default_factory=set)
    forbidden_item_ids: set[str] = field(default_factory=set)
    required_facets: set[ContextFacet] = field(default_factory=set)
    required_terms: set[str] = field(default_factory=set)
    max_items: int | None = None
    max_markdown_chars: int | None = None
    require_source_metadata: bool = False


@dataclass(frozen=True)
class ContextPackEvalResult:
    """Result from evaluating one context pack against one fixture."""

    fixture: str
    passed: bool
    failures: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


def _quality_value(item: ContextItem, key: str) -> Any:
    quality = getattr(item, "quality", None)
    if isinstance(quality, dict):
        return quality.get(key)
    return getattr(quality, key, None)


def _has_source_metadata(item: ContextItem) -> bool:
    metadata = item.metadata or {}
    return any(
        value
        for value in (
            item.source,
            metadata.get("source_id"),
            metadata.get("source"),
            metadata.get("source_file"),
            metadata.get("url"),
            _quality_value(item, "source"),
            _quality_value(item, "url"),
        )
    )


def _searchable_text(pack: ContextPack) -> str:
    chunks: list[str] = [pack.goal, pack.query, pack.domain or "", pack.project or ""]
    for item in pack.items:
        chunks.extend([item.name, item.content, item.reason, item.source or ""])
    return "\n".join(chunks).lower()


def evaluate_context_pack(
    pack: ContextPack,
    fixture: ContextPackFixture,
) -> ContextPackEvalResult:
    """Evaluate whether a context pack satisfies a dogfood fixture."""

    failures: list[str] = []
    item_ids = {item.id for item in pack.items}
    facets = {section.facet for section in pack.sections}

    missing_ids = sorted(fixture.required_item_ids - item_ids)
    if missing_ids:
        failures.append(f"missing required items: {', '.join(missing_ids)}")

    forbidden_ids = sorted(fixture.forbidden_item_ids & item_ids)
    if forbidden_ids:
        failures.append(f"forbidden items present: {', '.join(forbidden_ids)}")

    missing_facets = sorted(facet.value for facet in fixture.required_facets - facets)
    if missing_facets:
        failures.append(f"missing required facets: {', '.join(missing_facets)}")

    if fixture.max_items is not None and pack.total_items > fixture.max_items:
        failures.append(f"too many items: {pack.total_items} > {fixture.max_items}")

    markdown = context_pack_to_markdown(pack, max_items=max(pack.total_items, 1))
    if fixture.max_markdown_chars is not None and len(markdown) > fixture.max_markdown_chars:
        failures.append(
            f"markdown too large: {len(markdown)} chars > {fixture.max_markdown_chars}"
        )

    text = _searchable_text(pack)
    missing_terms = sorted(
        term for term in fixture.required_terms if term.lower() not in text
    )
    if missing_terms:
        failures.append(f"missing required terms: {', '.join(missing_terms)}")

    if fixture.require_source_metadata:
        unsourced = sorted(item.id for item in pack.items if not _has_source_metadata(item))
        if unsourced:
            failures.append(f"items missing source metadata: {', '.join(unsourced)}")

    metrics = {
        "items": pack.total_items,
        "facets": sorted(facet.value for facet in facets),
        "markdown_chars": len(markdown),
        "required_item_coverage": (
            1.0
            if not fixture.required_item_ids
            else (len(fixture.required_item_ids) - len(missing_ids))
            / len(fixture.required_item_ids)
        ),
    }
    return ContextPackEvalResult(
        fixture=fixture.name,
        passed=not failures,
        failures=failures,
        metrics=metrics,
    )


__all__ = [
    "ContextPackEvalResult",
    "ContextPackFixture",
    "evaluate_context_pack",
]
