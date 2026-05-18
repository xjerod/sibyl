from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from sibyl.ingestion.extractor import ExtractedEntity, ExtractedEntityType
from sibyl.ingestion.relationships import ExtractedRelationship, RelationType
from sibyl.ingestion.storage import store_entities, store_relationships


def _extracted_entity(name: str) -> ExtractedEntity:
    return ExtractedEntity(
        entity_type=ExtractedEntityType.CONCEPT,
        name=name,
        description=f"{name} description",
        confidence=0.9,
        source_episode_id="episode-1",
        context=f"{name} context",
    )


@pytest.mark.asyncio
async def test_store_entities_uses_native_runtime() -> None:
    entity_manager = SimpleNamespace(create=AsyncMock(return_value="entity-native"))
    runtime = SimpleNamespace(entity_manager=entity_manager)

    with patch(
        "sibyl.ingestion.storage._get_graph_runtime",
        new=AsyncMock(return_value=runtime),
    ) as get_runtime:
        entity_ids, errors = await store_entities(
            [_extracted_entity("Native Runtime")],
            group_id="org-native",
        )

    assert errors == []
    assert entity_ids == {"native runtime": "entity-native"}
    get_runtime.assert_awaited_once_with("org-native")
    entity_manager.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_store_relationships_uses_native_runtime() -> None:
    relationship_manager = SimpleNamespace(create=AsyncMock())
    runtime = SimpleNamespace(relationship_manager=relationship_manager)
    relationship = ExtractedRelationship(
        source_name="Source",
        target_name="Target",
        relation_type=RelationType.RELATED_TO,
        confidence=0.75,
        source_episode_id="episode-1",
        evidence="Source and target appear together.",
    )

    with patch(
        "sibyl.ingestion.storage._get_graph_runtime",
        new=AsyncMock(return_value=runtime),
    ) as get_runtime:
        stored, skipped, errors = await store_relationships(
            [relationship],
            {"source": "entity-source", "target": "entity-target"},
            group_id="org-native",
        )

    assert stored == 1
    assert skipped == 0
    assert errors == []
    get_runtime.assert_awaited_once_with("org-native")
    relationship_manager.create.assert_awaited_once()
    created_relationship = relationship_manager.create.await_args.args[0]
    assert created_relationship.source_id == "entity-source"
    assert created_relationship.target_id == "entity-target"
