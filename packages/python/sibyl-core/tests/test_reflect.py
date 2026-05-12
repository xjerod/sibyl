from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from sibyl_core.tools.reflect import (
    reflect_memory,
    reflection_pack_to_dict,
    reflection_pack_to_markdown,
)
from sibyl_core.tools.responses import AddResponse


@pytest.mark.asyncio
async def test_reflect_memory_extracts_domain_general_candidates() -> None:
    pack = await reflect_memory(
        "We decided to keep one Hyperbliss Technologies org. "
        "Next we will build reflect so agents remember planning sessions. "
        "Maybe context packs should score decisions above loose notes. "
        "Validated docs/architecture/SURREALDB_NATIVE_GOAL_STATE.md as the source.",
        source_title="Surreal planning",
        intent="plan",
        domain="sibyl",
        project="project_123",
        organization_id="org_123",
    )

    kinds = {candidate.kind for candidate in pack.candidates}

    assert {"decision", "plan", "idea", "artifact"} <= kinds
    assert pack.project == "project_123"
    assert pack.total_candidates == len(pack.candidates)
    assert all(candidate.metadata["project_id"] == "project_123" for candidate in pack.candidates)


@pytest.mark.asyncio
async def test_reflect_memory_can_persist_candidates_with_provenance() -> None:
    calls: list[dict[str, Any]] = []

    async def fake_add(**kwargs: Any) -> AddResponse:
        calls.append(kwargs)
        return AddResponse(
            success=True,
            id=f"{kwargs['entity_type']}_{len(calls)}",
            message="ok",
            timestamp=datetime.now(UTC),
        )

    pack = await reflect_memory(
        "Confirmed the local Sibyl project is linked. We will migrate it to Cloud later.",
        source_title="Dogfood setup",
        intent="build",
        domain="sibyl",
        project="project_123",
        related_to=["project_123"],
        organization_id="org_123",
        persist=True,
        add_fn=fake_add,
    )

    assert pack.persisted_count == len(pack.candidates)
    assert pack.source_id == "session_1"
    assert calls[0]["entity_type"] == "session"
    assert calls[0]["content"].startswith("Confirmed the local Sibyl project")
    assert calls[0]["metadata"]["reflection_source"] is True
    assert calls[1]["metadata"]["organization_id"] == "org_123"
    assert calls[1]["metadata"]["capture_mode"] == "reflect"
    assert calls[1]["metadata"]["project_id"] == "project_123"
    assert calls[1]["metadata"]["reflection_source_id"] == "session_1"
    assert calls[1]["related_to"] == ["project_123", "session_1"]
    assert calls[1]["sync"] is True


@pytest.mark.asyncio
async def test_reflect_memory_native_write_uses_policy_and_direct_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_entities = []
    created_relationships = []
    add_fn = AsyncMock(side_effect=AssertionError("compatibility add path should not run"))

    class FakeEntityManager:
        async def create_direct(self, entity):
            created_entities.append(entity)
            return entity.id

    class FakeRelationshipManager:
        async def create_bulk(self, relationships):
            created_relationships.extend(relationships)
            return len(relationships), 0

    async def fake_get_graph_runtime(_organization_id: str):
        return type(
            "Runtime",
            (),
            {
                "entity_manager": FakeEntityManager(),
                "relationship_manager": FakeRelationshipManager(),
            },
        )()

    monkeypatch.setenv("SIBYL_NATIVE_WRITE", "enabled")
    monkeypatch.setattr(
        "sibyl_core.services.native_memory.get_graph_runtime",
        fake_get_graph_runtime,
    )

    pack = await reflect_memory(
        "We decided native reflection writes should bypass Graphiti add_episode.",
        source_title="Native reflection",
        intent="build",
        domain="sibyl",
        project="project_123",
        related_to=["task_123"],
        organization_id="org_123",
        principal_id="user_123",
        accessible_projects={"project_123"},
        persist=True,
        add_fn=add_fn,
    )

    assert pack.source_id is not None
    assert pack.persisted_count == len(pack.candidates)
    assert add_fn.await_count == 0
    assert len(created_entities) == 2
    assert {entity.entity_type.value for entity in created_entities} == {"session", "decision"}
    assert created_entities[1].metadata["policy_allowed"] is True
    assert created_entities[1].metadata["policy_reasons"] == [
        "same_scope_reflect_allowed",
        "same_scope_write_allowed",
    ]
    assert created_entities[1].metadata["raw_source_ids"] == [pack.source_id]
    assert {relationship.relationship_type.value for relationship in created_relationships} >= {
        "BELONGS_TO",
        "DERIVED_FROM",
        "RELATED_TO",
    }


@pytest.mark.asyncio
async def test_reflect_memory_native_write_denies_unverified_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    add_fn = AsyncMock(side_effect=AssertionError("compatibility add path should not run"))
    create_direct = AsyncMock()

    async def fake_get_graph_runtime(_organization_id: str):
        return type(
            "Runtime",
            (),
            {
                "entity_manager": type("EntityManager", (), {"create_direct": create_direct})(),
                "relationship_manager": type(
                    "RelationshipManager",
                    (),
                    {"create_bulk": AsyncMock()},
                )(),
            },
        )()

    monkeypatch.setenv("SIBYL_NATIVE_WRITE", "enabled")
    monkeypatch.setattr(
        "sibyl_core.services.native_memory.get_graph_runtime",
        fake_get_graph_runtime,
    )

    pack = await reflect_memory(
        "We decided unauthorized project writes must fail closed.",
        source_title="Denied reflection",
        intent="build",
        domain="sibyl",
        project="project_123",
        organization_id="org_123",
        principal_id="user_123",
        accessible_projects={"project_other"},
        persist=True,
        add_fn=add_fn,
    )

    assert pack.source_id is None
    assert pack.persisted_count == 0
    assert add_fn.await_count == 0
    create_direct.assert_not_awaited()
    assert pack.candidates[0].metadata["policy_allowed"] is False
    assert pack.candidates[0].metadata["policy_reasons"] == [
        "unverified_membership",
        "unverified_membership",
    ]


@pytest.mark.asyncio
async def test_reflect_memory_requires_content_and_org_when_persisting() -> None:
    with pytest.raises(ValueError, match="content is required"):
        await reflect_memory("")

    with pytest.raises(ValueError, match="organization_id is required"):
        await reflect_memory("We decided this matters.", persist=True)


@pytest.mark.asyncio
async def test_reflection_pack_serializes_and_renders_markdown() -> None:
    pack = await reflect_memory("We decided to build reflect.", source_title="Planning")

    payload = reflection_pack_to_dict(pack)
    markdown = reflection_pack_to_markdown(pack)

    assert payload["source_title"] == "Planning"
    assert payload["candidates"][0]["kind"] == "decision"
    assert "# Sibyl Reflection: Planning" in markdown
    assert "Source:" not in markdown
    assert "## Decision:" in markdown
