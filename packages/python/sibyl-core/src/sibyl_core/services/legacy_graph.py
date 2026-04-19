"""Legacy graph runtime helpers for higher-level service layers."""

from dataclasses import dataclass
from typing import Any

from sibyl_core.models.entities import EntityType


@dataclass(frozen=True)
class LegacyGraphRuntime:
    """Bound legacy graph collaborators for a single organization."""

    client: Any
    entity_manager: Any
    relationship_manager: Any


async def get_legacy_graph_client() -> Any:
    """Return the shared legacy graph client."""

    from sibyl_core.graph.client import get_graph_client

    return await get_graph_client()


async def get_legacy_graph_runtime(group_id: str) -> LegacyGraphRuntime:
    """Bind the legacy graph managers for a single organization."""

    from sibyl_core.graph.entities import EntityManager
    from sibyl_core.graph.relationships import RelationshipManager

    client = await get_legacy_graph_client()
    return LegacyGraphRuntime(
        client=client,
        entity_manager=EntityManager(client, group_id=group_id),
        relationship_manager=RelationshipManager(client, group_id=group_id),
    )


async def count_entities_by_type(
    entity_manager: Any,
    *,
    include_archived: bool = False,
    page_size: int = 1000,
) -> dict[str, int]:
    """Count entities by type without assuming backend-specific aggregations."""

    counts = {entity_type.value: 0 for entity_type in EntityType}
    offset = 0

    while True:
        entities = await entity_manager.list_all(
            limit=page_size,
            offset=offset,
            include_archived=include_archived,
        )
        if not entities:
            break

        for entity in entities:
            counts[entity.entity_type.value] = counts.get(entity.entity_type.value, 0) + 1

        offset += len(entities)

    return counts


async def execute_legacy_graph_query(
    group_id: str,
    query: str,
    **params: Any,
) -> list[dict[str, Any]]:
    """Execute a raw org-scoped legacy graph query and normalize the result."""

    client = await get_legacy_graph_client()
    driver = client.client.driver.clone(group_id)
    result = await driver.execute_query(query, **params)
    return client.normalize_result(result)
