"""Native graph runtime helpers for higher-level service layers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from sibyl_core.models.entities import EntityType
from sibyl_core.services.native_graph import (
    NativeEntityManager,
    NativeRelationshipManager,
    NativeSurrealGraphClient,
    get_native_graph_client,
    get_native_graph_runtime,
    normalize_records,
)
from sibyl_core.utils.query import upper_query_tokens


class EntityRecordLike(Protocol):
    entity_type: EntityType


class EntityManagerLike(Protocol):
    async def list_all(
        self,
        *,
        limit: int,
        offset: int,
        include_archived: bool,
    ) -> Sequence[EntityRecordLike]: ...


@dataclass(frozen=True)
class ActiveGraphRuntime:
    """Bound graph collaborators for a single organization."""

    client: NativeSurrealGraphClient
    entity_manager: NativeEntityManager
    relationship_manager: NativeRelationshipManager


def _query_tokens(query: str) -> set[str]:
    return upper_query_tokens(query)


def _assert_surreal_query_dialect(query: str) -> None:
    if not _query_tokens(query).isdisjoint({"CALL", "MATCH", "UNWIND"}):
        raise ValueError("Surreal runtime graph queries must use SurrealQL")


async def get_graph_client(group_id: str = "default") -> NativeSurrealGraphClient:
    """Return the native graph client for the requested organization."""

    client = await get_native_graph_client(str(group_id))
    await client.connect()
    return client


async def get_graph_runtime(group_id: str) -> ActiveGraphRuntime:
    """Bind the native graph managers for a single organization."""

    runtime = await get_native_graph_runtime(str(group_id))
    return ActiveGraphRuntime(
        client=runtime.client,
        entity_manager=runtime.entity_manager,
        relationship_manager=runtime.relationship_manager,
    )


async def count_entities_by_type(
    entity_manager: EntityManagerLike,
    *,
    include_archived: bool = False,
    page_size: int = 1000,
) -> dict[str, int]:
    """Count entities by type without assuming backend-specific aggregations."""

    native_counter = getattr(entity_manager, "count_by_type", None)
    if callable(native_counter):
        return await native_counter(include_archived=include_archived)

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


async def execute_graph_query(
    group_id: str,
    query: str,
    **params: object,
) -> list[dict[str, object]]:
    """Execute a raw org-scoped graph query and normalize the result."""

    runtime = await get_graph_runtime(str(group_id))
    _assert_surreal_query_dialect(query)
    result = await runtime.client.execute_query(query, group_id=str(group_id), **params)
    return normalize_records(result)
