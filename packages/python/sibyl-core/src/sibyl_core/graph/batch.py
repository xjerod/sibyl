"""Batch graph operations routed through backend-aware managers.

This module provides utilities for creating, updating, and deleting multiple
graph records without exposing callers to the active graph dialect.

Instead of:
    for entity in entities:
        await node.save(driver)  # N separate queries

Use:
    await batch_create_nodes(driver, org_id, nodes)  # 1 query for all

Performance:
    Sequential: ~100ms per entity = 10s for 100 entities
    Manager-backed batch: backend-specific write path with one public call site
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import structlog

from sibyl_core.graph.entities import EntityManager
from sibyl_core.graph.relationships import RelationshipManager
from sibyl_core.models.entities import Entity, EntityType, Relationship, RelationshipType

if TYPE_CHECKING:
    from sibyl_core.graph.client import GraphClient

log = structlog.get_logger()


async def batch_create_nodes(
    client: GraphClient,
    organization_id: str,
    nodes: list[dict[str, Any]],
    *,
    label: str = "Entity",
    return_ids: bool = True,
) -> list[str]:
    """Create multiple graph nodes through the active EntityManager.

    Args:
        client: GraphClient instance.
        organization_id: Org UUID for graph scoping.
        nodes: List of node dictionaries with properties.
            Each dict must have 'uuid' and 'name' keys.
        label: Primary node label (default: "Entity").
        return_ids: Whether to return created UUIDs.

    Returns:
        List of created node UUIDs (if return_ids=True), else empty list.

    Example:
        nodes = [
            {"uuid": "id1", "name": "Task 1", "entity_type": "task", ...},
            {"uuid": "id2", "name": "Task 2", "entity_type": "task", ...},
        ]
        ids = await batch_create_nodes(client, org_id, nodes)
    """
    if not nodes:
        return []

    # Ensure all nodes have required fields
    for i, node in enumerate(nodes):
        if "uuid" not in node:
            raise ValueError(f"Node at index {i} missing required 'uuid' field")
        if "name" not in node:
            raise ValueError(f"Node at index {i} missing required 'name' field")

    entity_manager = EntityManager(client, group_id=organization_id)

    try:
        ids: list[str] = []
        for node in nodes:
            entity = _node_to_entity(node, label=label)
            entity_id = await entity_manager.create(entity)
            if return_ids:
                ids.append(entity_id)
        return ids

    except Exception as e:
        log.error(
            "batch_create_nodes failed",
            org_id=organization_id,
            node_count=len(nodes),
            error=str(e),
        )
        raise


async def batch_create_episodic_nodes(
    client: GraphClient,
    organization_id: str,
    episodes: list[dict[str, Any]],
    *,
    return_ids: bool = True,
) -> list[str]:
    """Create multiple Episodic nodes through the active EntityManager.

    Specialized batch create for Episodic nodes (used by add_episode).

    Args:
        client: GraphClient instance.
        organization_id: Org UUID for graph scoping.
        episodes: List of episode dictionaries.
        return_ids: Whether to return created UUIDs.

    Returns:
        List of created episode UUIDs.
    """
    return await batch_create_nodes(
        client,
        organization_id,
        episodes,
        label="Episodic",
        return_ids=return_ids,
    )


async def batch_create_relationships(
    client: GraphClient,
    organization_id: str,
    relationships: list[dict[str, Any]],
    *,
    rel_type: str = "RELATES_TO",
) -> int:
    """Create multiple relationships through the active RelationshipManager.

    Args:
        client: GraphClient instance.
        organization_id: Org UUID for graph scoping.
        relationships: List of relationship dicts with:
            - from_uuid: Source node UUID
            - to_uuid: Target node UUID
            - properties: Optional dict of relationship properties
        rel_type: Relationship type (default: "RELATES_TO")

    Returns:
        Number of relationships created.

    Example:
        rels = [
            {"from_uuid": "id1", "to_uuid": "id2", "properties": {"weight": 1.0}},
            {"from_uuid": "id1", "to_uuid": "id3"},
        ]
        count = await batch_create_relationships(client, org_id, rels)
    """
    if not relationships:
        return 0

    # Validate required fields
    for i, rel in enumerate(relationships):
        if "from_uuid" not in rel:
            raise ValueError(f"Relationship at index {i} missing 'from_uuid'")
        if "to_uuid" not in rel:
            raise ValueError(f"Relationship at index {i} missing 'to_uuid'")

    relationship_manager = RelationshipManager(client, group_id=organization_id)
    relationship_type = _normalize_relationship_type(rel_type)

    try:
        created = 0
        for rel in relationships:
            properties = dict(rel.get("properties", {}))
            weight = properties.pop("weight", 1.0)
            await relationship_manager.create(
                Relationship(
                    id=str(rel.get("uuid") or uuid4()),
                    source_id=str(rel["from_uuid"]),
                    target_id=str(rel["to_uuid"]),
                    relationship_type=relationship_type,
                    weight=float(weight),
                    metadata=properties,
                )
            )
            created += 1
        return created

    except Exception as e:
        log.error(
            "batch_create_relationships failed",
            org_id=organization_id,
            rel_count=len(relationships),
            error=str(e),
        )
        raise


async def batch_update_nodes(
    client: GraphClient,
    organization_id: str,
    updates: list[dict[str, Any]],
    *,
    label: str | None = None,
) -> int:
    """Update multiple nodes through the active EntityManager.

    Args:
        client: GraphClient instance.
        organization_id: Org UUID for graph scoping.
        updates: List of update dicts with:
            - uuid: Node UUID to update
            - properties: Dict of properties to set/update
        label: Optional label filter (only update nodes with this label).

    Returns:
        Number of nodes updated.

    Example:
        updates = [
            {"uuid": "id1", "properties": {"status": "done"}},
            {"uuid": "id2", "properties": {"status": "doing", "priority": "high"}},
        ]
        count = await batch_update_nodes(client, org_id, updates)
    """
    if not updates:
        return 0

    # Validate and serialize
    serialized = []
    for i, update in enumerate(updates):
        if "uuid" not in update:
            raise ValueError(f"Update at index {i} missing 'uuid'")
        if "properties" not in update:
            raise ValueError(f"Update at index {i} missing 'properties'")

        serialized.append(
            {
                "uuid": str(update["uuid"]),
                "properties": update["properties"],
            }
        )

    entity_manager = EntityManager(client, group_id=organization_id)

    try:
        updated = 0
        for update in serialized:
            if label:
                try:
                    existing = await entity_manager.get(update["uuid"])
                except Exception:
                    continue
                if not _entity_matches_label(existing, label):
                    continue
            if await entity_manager.update(update["uuid"], update["properties"]) is not None:
                updated += 1
        return updated

    except Exception as e:
        log.error(
            "batch_update_nodes failed",
            org_id=organization_id,
            update_count=len(updates),
            error=str(e),
        )
        raise


async def batch_delete_nodes(
    client: GraphClient,
    organization_id: str,
    uuids: list[str],
    *,
    label: str | None = None,
    detach: bool = True,
) -> int:
    """Delete multiple nodes through the active EntityManager.

    Args:
        client: GraphClient instance.
        organization_id: Org UUID for graph scoping.
        uuids: List of node UUIDs to delete.
        label: Optional label filter.
        detach: Kept for API compatibility; manager-backed deletes decide cascade behavior.

    Returns:
        Number of nodes deleted.
    """
    if not uuids:
        return 0

    entity_manager = EntityManager(client, group_id=organization_id)

    try:
        deleted = 0
        for entity_id in uuids:
            if label:
                try:
                    existing = await entity_manager.get(entity_id)
                except Exception:
                    continue
                if not _entity_matches_label(existing, label):
                    continue
            if not detach:
                # Manager-backed deletes already rely on backend cascade semantics.
                # The flag remains for API compatibility.
                pass
            if await entity_manager.delete(entity_id):
                deleted += 1
        return deleted

    except Exception as e:
        log.error(
            "batch_delete_nodes failed",
            org_id=organization_id,
            uuid_count=len(uuids),
            error=str(e),
        )
        raise


def _serialize_node(node: dict[str, Any], group_id: str) -> dict[str, Any]:
    """Serialize a node dict for legacy batch payload compatibility.

    Args:
        node: Node dictionary with properties.
        group_id: Organization ID to set as group_id.

    Returns:
        Serialized node dict with JSON-safe values.
    """
    result: dict[str, Any] = {
        "group_id": group_id,
        "created_at": datetime.now(UTC).isoformat(),
    }

    for key, value in node.items():
        result[key] = _serialize_value(value)

    return result


def _node_to_entity(
    node: dict[str, Any],
    *,
    label: str,
) -> Entity:
    entity_type = _infer_entity_type(node, label=label)
    metadata = dict(node.get("metadata") or {})
    excluded_keys = {
        "uuid",
        "name",
        "entity_type",
        "description",
        "content",
        "metadata",
        "created_at",
        "updated_at",
        "source_file",
        "embedding",
        "organization_id",
        "created_by",
        "modified_by",
    }
    metadata.update({key: value for key, value in node.items() if key not in excluded_keys})

    return Entity(
        id=str(node["uuid"]),
        entity_type=entity_type,
        name=str(node["name"]),
        description=str(node.get("description") or ""),
        content=str(node.get("content") or ""),
        organization_id=node.get("organization_id"),
        created_by=node.get("created_by"),
        modified_by=node.get("modified_by"),
        metadata=metadata,
        created_at=_coerce_datetime(node.get("created_at")),
        updated_at=_coerce_datetime(node.get("updated_at")),
        source_file=node.get("source_file"),
        embedding=node.get("embedding"),
    )


def _infer_entity_type(node: dict[str, Any], *, label: str) -> EntityType:
    entity_type = node.get("entity_type")
    if isinstance(entity_type, EntityType):
        return entity_type
    if isinstance(entity_type, str):
        with_value = entity_type.strip().lower()
        if with_value:
            try:
                return EntityType(with_value)
            except ValueError:
                pass

    normalized_label = label.strip().lower()
    if normalized_label == "episodic":
        return EntityType.EPISODE
    try:
        return EntityType(normalized_label)
    except ValueError:
        return EntityType.TOPIC


def _entity_matches_label(entity: Entity, label: str) -> bool:
    normalized_label = label.strip().lower()
    if normalized_label == "episodic":
        normalized_label = EntityType.EPISODE.value
    return entity.entity_type.value == normalized_label


def _normalize_relationship_type(rel_type: str) -> RelationshipType:
    normalized = rel_type.strip().upper()
    if normalized == "RELATES_TO":
        normalized = RelationshipType.RELATED_TO.value
    return RelationshipType(normalized)


def _coerce_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            parsed = None
        if parsed is not None:
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed
    return datetime.now(UTC)


def _serialize_properties(props: dict[str, Any]) -> dict[str, Any]:
    """Serialize a properties dict for legacy batch payload compatibility.

    Args:
        props: Properties dictionary.

    Returns:
        Serialized properties with JSON-safe values.
    """
    return {key: _serialize_value(value) for key, value in props.items()}


def _serialize_value(value: Any) -> Any:
    """Serialize a single value for legacy batch payload compatibility.

    Args:
        value: Value to serialize.

    Returns:
        Serialized JSON-safe value.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return json.dumps(value)
    if isinstance(value, list):
        # Check if list contains complex objects
        if value and isinstance(value[0], dict):
            return json.dumps(value)
        return value
    if hasattr(value, "value"):  # Enum
        return value.value
    return value
