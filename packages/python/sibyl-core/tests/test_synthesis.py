from __future__ import annotations

from typing import Any, Literal

import pytest

from sibyl_core.models.synthesis import (
    SynthesisOutputType,
    SynthesisRequest,
    SynthesisSectionRequest,
    SynthesisSourceReference,
    SynthesisVerificationStatus,
)
from sibyl_core.services.synthesis import plan_synthesis
from sibyl_core.tools.responses import SearchResponse, SearchResult


def _result(
    entity_id: str,
    entity_type: str,
    name: str,
    *,
    content: str | None = None,
    score: float = 0.8,
    origin: Literal["graph", "document"] = "graph",
    metadata: dict[str, Any] | None = None,
) -> SearchResult:
    return SearchResult(
        id=entity_id,
        type=entity_type,
        name=name,
        content=content or f"{name} content",
        score=score,
        source=f"source:{entity_id}",
        result_origin=origin,
        metadata={"entity_type": entity_type, **(metadata or {})},
    )


async def _empty_related(**kwargs: Any) -> list[SynthesisSourceReference]:
    return []


@pytest.mark.asyncio
async def test_plan_synthesis_builds_deterministic_source_aware_outline() -> None:
    calls: list[dict[str, Any]] = []
    responses = {
        ("decision",): [
            _result(
                "decision:source-law",
                "decision",
                "Require source citations",
                content="Every roadmap claim needs source IDs and visible provenance.",
                score=0.95,
            )
        ],
        ("task", "epic", "plan"): [
            _result(
                "task:d1",
                "task",
                "Implement synthesis planner",
                content="Next milestone is deterministic synthesis planning before drafting.",
                score=0.9,
            )
        ],
        ("artifact", "document", "source", "config_file"): [
            _result(
                "artifact:post-v08-plan",
                "artifact",
                "Post v0.8 synthesis plan",
                content="The roadmap moves from ingest into synthesis and cockpit work.",
                score=0.85,
            )
        ],
    }

    async def fake_search(**kwargs: Any) -> SearchResponse:
        calls.append(kwargs)
        results = responses.get(tuple(kwargs["types"]), [])
        return SearchResponse(
            results=results,
            total=len(results),
            query=kwargs["query"],
            filters={"types": kwargs["types"]},
        )

    request = SynthesisRequest(
        goal="Write the v0.9 roadmap",
        output_type=SynthesisOutputType.ROADMAP,
        seed_query="v0.9 synthesis roadmap",
        project="project-sibyl",
        domain="memory",
    )

    first = await plan_synthesis(
        request,
        organization_id="org-123",
        accessible_projects={"project-sibyl"},
        search_fn=fake_search,
        related_fn=_empty_related,
    )
    second = await plan_synthesis(
        request,
        organization_id="org-123",
        accessible_projects={"project-sibyl"},
        search_fn=fake_search,
        related_fn=_empty_related,
    )

    assert first.run_id == second.run_id
    assert [section.title for section in first.outline.sections] == [
        "Current State",
        "Completed Work",
        "Next Milestones",
        "Risks And Open Questions",
    ]
    assert first.verification.status == SynthesisVerificationStatus.PENDING
    assert first.verification.gap_count == 0
    assert first.source_packs[2].source_ids[0] == "task:d1"
    assert {call["organization_id"] for call in calls} == {"org-123"}
    assert {call["project"] for call in calls} == {"project-sibyl"}
    assert {frozenset(call["accessible_projects"]) for call in calls} == {
        frozenset({"project-sibyl"})
    }


@pytest.mark.asyncio
async def test_plan_synthesis_returns_gap_for_unsupported_required_section() -> None:
    async def fake_search(**kwargs: Any) -> SearchResponse:
        return SearchResponse(
            results=[
                _result(
                    "decision:database",
                    "decision",
                    "Use SurrealDB",
                    content="The database migration is complete.",
                )
            ],
            total=1,
            query=kwargs["query"],
            filters={"types": kwargs["types"]},
        )

    run = await plan_synthesis(
        SynthesisRequest(
            goal="Plan mobile launch",
            required_sections=[
                SynthesisSectionRequest(
                    title="Mobile Launch",
                    prompt="Describe the supported iOS and Android release plan.",
                )
            ],
        ),
        organization_id="org-123",
        search_fn=fake_search,
        related_fn=_empty_related,
    )

    assert run.verification.status == SynthesisVerificationStatus.GAPS
    assert run.verification.gaps[0].reason == "no_source_supports_requested_section"
    assert run.outline.sections[0].source_ids == []
    assert run.source_packs[0].sources == []


@pytest.mark.asyncio
async def test_plan_synthesis_reports_missing_required_sources_once() -> None:
    async def fake_search(**kwargs: Any) -> SearchResponse:
        return SearchResponse(results=[], total=0, query=kwargs["query"], filters={})

    run = await plan_synthesis(
        SynthesisRequest(
            goal="Write release notes",
            required_sections=[
                SynthesisSectionRequest(
                    title="Verification",
                    required_source_ids=["artifact:missing"],
                )
            ],
        ),
        organization_id="org-123",
        search_fn=fake_search,
        related_fn=_empty_related,
    )

    assert run.verification.gap_count == 1
    assert run.verification.gaps[0].reason == "required_source_ids_not_found"
    assert run.verification.gaps[0].missing_source_ids == ["artifact:missing"]


@pytest.mark.asyncio
async def test_plan_synthesis_uses_entity_ids_and_graph_neighborhoods() -> None:
    related_calls: list[str] = []

    async def fake_search(**kwargs: Any) -> SearchResponse:
        return SearchResponse(results=[], total=0, query=kwargs["query"], filters={})

    async def fake_related(**kwargs: Any) -> list[SynthesisSourceReference]:
        related_calls.append(kwargs["entity_id"])
        return [
            SynthesisSourceReference(
                id="task:neighbor",
                type="task",
                name="Neighbor task",
                content_preview="Follow-up task related to the seed decision.",
                score=0.5,
                origin="neighborhood",
                relation="RELATED_TO",
            )
        ]

    run = await plan_synthesis(
        SynthesisRequest(
            goal="Summarize the synthesis path",
            output_type=SynthesisOutputType.BRIEFING,
            entity_ids=["decision:root"],
        ),
        organization_id="org-123",
        search_fn=fake_search,
        related_fn=fake_related,
    )

    all_source_ids = {
        source_id for pack in run.source_packs for source_id in pack.source_ids
    }
    assert related_calls == ["decision:root"]
    assert "decision:root" in all_source_ids
    assert "task:neighbor" in all_source_ids
