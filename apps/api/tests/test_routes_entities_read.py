from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from sibyl.api.routes.entities import get_entity
from sibyl_core.models.entities import Entity, EntityType, Relationship, RelationshipType
from sibyl_core.storage import EntityBundle


@pytest.mark.asyncio
async def test_get_entity_uses_knowledge_service_for_graph_entities() -> None:
    org = SimpleNamespace(id=UUID("00000000-0000-0000-0000-000000000111"))
    task = Entity(
        id="task-1",
        entity_type=EntityType.TASK,
        name="Ship the seam",
        metadata={"priority": "high"},
    )
    project = Entity(
        id="project-1",
        entity_type=EntityType.PROJECT,
        name="Sibyl Native",
    )
    relationship = Relationship(
        id="rel-1",
        relationship_type=RelationshipType.BELONGS_TO,
        source_id="task-1",
        target_id="project-1",
    )
    service = AsyncMock()
    service.get_entity_bundle.return_value = EntityBundle(
        entity=task,
        relationships=[relationship],
        related_entities=[project],
    )

    with patch(
        "sibyl.api.routes.entities.get_legacy_entity_runtime",
        AsyncMock(),
    ) as get_legacy_entity_runtime:
        response = await get_entity("task-1", org=org, service=service)

    assert response.id == "task-1"
    assert response.metadata["priority"] == "high"
    assert response.related is not None
    assert response.related[0].id == "project-1"
    assert response.related[0].relationship == "BELONGS_TO"
    service.get_entity_bundle.assert_awaited_once_with("task-1")
    get_legacy_entity_runtime.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_entity_keeps_project_summary_enrichment() -> None:
    org = SimpleNamespace(id=UUID("00000000-0000-0000-0000-000000000111"))
    project = Entity(
        id="project-1",
        entity_type=EntityType.PROJECT,
        name="Sibyl Native",
        metadata={"status": "active"},
    )
    service = AsyncMock()
    service.get_entity_bundle.return_value = EntityBundle(entity=project)
    manager = MagicMock()
    manager.get_project_summary = AsyncMock(
        return_value={
            "total_tasks": 3,
            "status_counts": {"todo": 2, "doing": 1},
            "progress_pct": 33.3,
            "critical_tasks": [],
            "epics": [],
            "actionable_tasks": [
                {
                    "id": "task-1",
                    "name": "Ship graph seam",
                    "status": "doing",
                }
            ],
        }
    )
    runtime = SimpleNamespace(entity_manager=manager, relationship_manager=MagicMock())

    with patch(
        "sibyl.api.routes.entities.get_legacy_entity_runtime",
        AsyncMock(return_value=runtime),
    ):
        response = await get_entity("project-1", org=org, service=service)

    assert response.id == "project-1"
    assert response.metadata["total_tasks"] == 3
    assert response.metadata["actionable_tasks"][0]["id"] == "task-1"
    assert response.related is not None
    assert response.related[0].id == "task-1"
    assert response.related[0].relationship == "doing"


@pytest.mark.asyncio
async def test_get_entity_graph_mode_skips_bundle_loading() -> None:
    org = SimpleNamespace(id=UUID("00000000-0000-0000-0000-000000000111"))
    task = Entity(
        id="task-1",
        entity_type=EntityType.TASK,
        name="Ship the seam",
        metadata={"priority": "high"},
    )
    service = AsyncMock()
    service.get_entity.return_value = task

    with patch(
        "sibyl.api.routes.entities.get_legacy_entity_runtime",
        AsyncMock(),
    ) as get_legacy_entity_runtime:
        response = await get_entity(
            "task-1",
            org=org,
            service=service,
            include_summary=False,
            related_limit=0,
        )

    assert response.id == "task-1"
    assert response.metadata["priority"] == "high"
    assert response.related is None
    service.get_entity.assert_awaited_once_with("task-1")
    service.get_entity_bundle.assert_not_awaited()
    get_legacy_entity_runtime.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_entity_preserves_preloaded_project_related_context() -> None:
    org = SimpleNamespace(id=UUID("00000000-0000-0000-0000-000000000111"))
    project = Entity(
        id="project-1",
        entity_type=EntityType.PROJECT,
        name="Sibyl Native",
        metadata={"status": "active"},
    )
    pattern = Entity(
        id="pattern-1",
        entity_type=EntityType.PATTERN,
        name="Prefer graph-light sidebars",
    )
    relationship = Relationship(
        id="rel-1",
        relationship_type=RelationshipType.RELATED_TO,
        source_id="project-1",
        target_id="pattern-1",
    )
    service = AsyncMock()
    service.get_entity_bundle.return_value = EntityBundle(
        entity=project,
        relationships=[relationship],
        related_entities=[pattern],
    )
    manager = MagicMock()
    manager.get_project_summary = AsyncMock(
        return_value={
            "total_tasks": 3,
            "status_counts": {"todo": 2, "doing": 1},
            "progress_pct": 33.3,
            "critical_tasks": [],
            "epics": [],
            "actionable_tasks": [
                {
                    "id": "task-1",
                    "name": "Ship graph seam",
                    "status": "doing",
                }
            ],
        }
    )
    runtime = SimpleNamespace(entity_manager=manager, relationship_manager=MagicMock())

    with patch(
        "sibyl.api.routes.entities.get_legacy_entity_runtime",
        AsyncMock(return_value=runtime),
    ):
        response = await get_entity("project-1", org=org, service=service)

    assert response.related is not None
    assert [rel.id for rel in response.related] == ["pattern-1"]
    assert response.metadata["actionable_tasks"][0]["id"] == "task-1"
