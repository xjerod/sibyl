from __future__ import annotations

from typing import Any, Literal

import pytest

from sibyl_core.evals import ContextPackFixture, evaluate_context_pack
from sibyl_core.models.context import (
    ContextFacet,
    ContextIntent,
    ContextItem,
    ContextPack,
    ContextSection,
)
from sibyl_core.tools.context import compile_context
from sibyl_core.tools.responses import SearchResponse, SearchResult


def _result(
    entity_id: str,
    entity_type: str,
    name: str,
    content: str,
    *,
    score: float = 0.9,
    source: str | None = "seeded fixture",
    result_origin: Literal["graph", "document"] = "graph",
    metadata: dict[str, Any] | None = None,
) -> SearchResult:
    return SearchResult(
        id=entity_id,
        type=entity_type,
        name=name,
        content=content,
        score=score,
        source=source,
        result_origin=result_origin,
        metadata={"entity_type": entity_type, "source_id": f"src-{entity_id}", **(metadata or {})},
    )


@pytest.mark.asyncio
async def test_context_pack_fixture_passes_coding_handoff_requirements() -> None:
    async def fake_search(**kwargs: Any) -> SearchResponse:
        by_types = {
            ("task", "epic", "project"): [
                _result(
                    "task-active",
                    "task",
                    "Implement native RawMemory slice",
                    "Current task is the native RawMemory baseline for scoped recall.",
                    metadata={"project_id": "project-sibyl"},
                )
            ],
            ("decision",): [
                _result(
                    "decision-source-law",
                    "decision",
                    "Raw memory stays source-grounded",
                    "Decision: preserve source IDs before extraction or graph traversal.",
                    metadata={"project_id": "project-sibyl"},
                )
            ],
            ("artifact", "document", "source", "config_file"): [
                _result(
                    "artifact-test",
                    "artifact",
                    "Context pack tests",
                    "Relevant tests include test_context_pack and test_context_pack_evals.",
                    result_origin="document",
                    metadata={"project_id": "project-sibyl"},
                )
            ],
            ("error_pattern", "pattern"): [
                _result(
                    "risk-privacy",
                    "pattern",
                    "Remaining risk: private memory leakage",
                    "Remaining risk is leaking private memory into project context packs.",
                    metadata={"project_id": "project-sibyl"},
                )
            ],
        }
        results = by_types.get(tuple(kwargs["types"] or ()), [])
        return SearchResponse(
            results=results,
            total=len(results),
            query=kwargs["query"],
            filters={"types": kwargs["types"]},
        )

    pack = await compile_context(
        "handoff the native memory implementation",
        intent="build",
        domain="sibyl",
        project="project-sibyl",
        organization_id="org-hyperbliss",
        search_fn=fake_search,
    )

    result = evaluate_context_pack(
        pack,
        ContextPackFixture(
            name="coding-handoff",
            required_item_ids={"task-active", "decision-source-law", "artifact-test"},
            required_facets={
                ContextFacet.ACTIVE_WORK,
                ContextFacet.DECISIONS,
                ContextFacet.ARTIFACTS,
            },
            required_terms={"remaining risk", "test_context_pack"},
            max_items=8,
            max_markdown_chars=5000,
            require_source_metadata=True,
        ),
    )

    assert result.passed, result.failures
    assert result.metrics["required_item_coverage"] == 1.0
    assert result.metrics["items"] == 4


@pytest.mark.asyncio
async def test_context_pack_fixture_passes_haven_privacy_requirements() -> None:
    async def fake_search(**kwargs: Any) -> SearchResponse:
        if kwargs["types"] == ["domain", "topic", "claim"]:
            results = [
                _result(
                    "haven-routine-evening",
                    "claim",
                    "Evening routine preference",
                    "Bliss prefers the hallway lights dimmed during evening wind-down.",
                    metadata={
                        "project_id": "project-haven",
                        "memory_space": "household",
                    },
                )
            ]
        else:
            results = []
        return SearchResponse(
            results=results,
            total=len(results),
            query=kwargs["query"],
            filters={"types": kwargs["types"]},
        )

    pack = await compile_context(
        "what should Haven remember about the evening routine?",
        intent="research",
        domain="haven",
        project="project-haven",
        organization_id="org-home",
        search_fn=fake_search,
    )

    result = evaluate_context_pack(
        pack,
        ContextPackFixture(
            name="haven-private-home-routine",
            required_item_ids={"haven-routine-evening"},
            forbidden_item_ids={"private-unrelated-medical-note"},
            required_facets={ContextFacet.DOMAIN},
            required_terms={"evening", "hallway lights"},
            max_items=4,
            require_source_metadata=True,
        ),
    )

    assert result.passed, result.failures


@pytest.mark.asyncio
async def test_context_pack_fixture_reports_forbidden_haven_memory_leak() -> None:
    async def fake_search(**kwargs: Any) -> SearchResponse:
        if kwargs["types"] == ["domain", "topic", "claim"]:
            results = [
                _result(
                    "haven-routine-evening",
                    "claim",
                    "Evening routine preference",
                    "Bliss prefers the hallway lights dimmed during evening wind-down.",
                ),
                _result(
                    "private-unrelated-medical-note",
                    "claim",
                    "Private unrelated health note",
                    "This private health note must not appear in Haven household recall.",
                ),
            ]
        else:
            results = []
        return SearchResponse(
            results=results,
            total=len(results),
            query=kwargs["query"],
            filters={"types": kwargs["types"]},
        )

    pack = await compile_context(
        "what should Haven remember about the evening routine?",
        intent="research",
        domain="haven",
        project="project-haven",
        organization_id="org-home",
        search_fn=fake_search,
    )

    result = evaluate_context_pack(
        pack,
        ContextPackFixture(
            name="haven-private-home-routine",
            required_item_ids={"haven-routine-evening"},
            forbidden_item_ids={"private-unrelated-medical-note"},
        ),
    )

    assert not result.passed
    assert result.failures == ["forbidden items present: private-unrelated-medical-note"]


def test_context_pack_fixture_reports_missing_source_metadata() -> None:
    item = ContextItem(
        id="unsourced-memory",
        type="decision",
        name="Unsourced decision",
        content="This decision is missing provenance.",
        score=0.9,
        facet=ContextFacet.DECISIONS,
        reason="decision records a choice or rationale the agent should preserve",
        source=None,
        metadata={},
    )
    pack = ContextPack(
        goal="evaluate provenance",
        intent=ContextIntent.DECIDE,
        query="evaluate provenance",
        domain="sibyl",
        project="project-sibyl",
        sections=[
            ContextSection(
                facet=ContextFacet.DECISIONS,
                title="Decisions",
                items=[item],
            )
        ],
        total_items=1,
    )

    result = evaluate_context_pack(
        pack,
        ContextPackFixture(
            name="source-grounded-context",
            required_item_ids={"unsourced-memory"},
            require_source_metadata=True,
        ),
    )

    assert not result.passed
    assert result.failures == ["items missing source metadata: unsourced-memory"]
