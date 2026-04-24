"""Tests for batch graph operations using UNWIND.

Covers the batch utility functions that create, update, and delete
multiple nodes/relationships in single queries.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from sibyl_core.graph.batch import (
    _serialize_node,
    _serialize_properties,
    _serialize_value,
    batch_create_nodes,
    batch_create_relationships,
    batch_delete_nodes,
    batch_update_nodes,
)
from sibyl_core.models.entities import Entity, EntityType, RelationshipType


# =============================================================================
# Fixtures
# =============================================================================
@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock GraphClient."""
    return MagicMock()


@pytest.fixture
def org_id() -> str:
    """Generate a unique organization ID."""
    return str(uuid4())


@pytest.fixture
def sample_nodes() -> list[dict[str, Any]]:
    """Generate sample node data for testing."""
    return [
        {
            "uuid": str(uuid4()),
            "name": "Task 1",
            "entity_type": "task",
            "description": "First task",
        },
        {
            "uuid": str(uuid4()),
            "name": "Task 2",
            "entity_type": "task",
            "description": "Second task",
        },
        {
            "uuid": str(uuid4()),
            "name": "Task 3",
            "entity_type": "task",
            "description": "Third task",
        },
    ]


# =============================================================================
# batch_create_nodes Tests
# =============================================================================
class TestBatchCreateNodes:
    """Tests for batch_create_nodes function."""

    @pytest.mark.asyncio
    async def test_creates_nodes_with_unwind(
        self, mock_client: MagicMock, org_id: str, sample_nodes: list[dict]
    ) -> None:
        """Creates multiple nodes through EntityManager."""
        entity_manager = MagicMock()
        entity_manager.create = AsyncMock(side_effect=[node["uuid"] for node in sample_nodes])

        with patch("sibyl_core.graph.batch.EntityManager", return_value=entity_manager):
            result = await batch_create_nodes(mock_client, org_id, sample_nodes)

        assert len(result) == 3
        assert entity_manager.create.await_count == 3
        first_entity = entity_manager.create.await_args_list[0].args[0]
        assert first_entity.id == sample_nodes[0]["uuid"]
        assert first_entity.entity_type == EntityType.TASK

    @pytest.mark.asyncio
    async def test_empty_list_returns_empty(self, mock_client: MagicMock, org_id: str) -> None:
        """Empty input returns empty list without query."""
        result = await batch_create_nodes(mock_client, org_id, [])
        assert result == []
        mock_client.execute_write_org.assert_not_called()

    @pytest.mark.asyncio
    async def test_validates_required_uuid(self, mock_client: MagicMock, org_id: str) -> None:
        """Raises ValueError if node missing uuid."""
        nodes = [{"name": "Missing UUID"}]

        with pytest.raises(ValueError, match="missing required 'uuid'"):
            await batch_create_nodes(mock_client, org_id, nodes)

    @pytest.mark.asyncio
    async def test_validates_required_name(self, mock_client: MagicMock, org_id: str) -> None:
        """Raises ValueError if node missing name."""
        nodes = [{"uuid": str(uuid4())}]

        with pytest.raises(ValueError, match="missing required 'name'"):
            await batch_create_nodes(mock_client, org_id, nodes)

    @pytest.mark.asyncio
    async def test_uses_custom_label(
        self, mock_client: MagicMock, org_id: str, sample_nodes: list[dict]
    ) -> None:
        """Infers entity type from label when node data omits it."""
        entity_manager = MagicMock()
        entity_manager.create = AsyncMock(return_value="task-1")
        nodes = [{"uuid": "task-1", "name": "Task 1"}]

        with patch("sibyl_core.graph.batch.EntityManager", return_value=entity_manager):
            await batch_create_nodes(mock_client, org_id, nodes, label="Task", return_ids=False)

        created_entity = entity_manager.create.await_args.args[0]
        assert created_entity.entity_type == EntityType.TASK

    @pytest.mark.asyncio
    async def test_no_return_when_return_ids_false(
        self, mock_client: MagicMock, org_id: str, sample_nodes: list[dict]
    ) -> None:
        """Does not return ids when requested."""
        entity_manager = MagicMock()
        entity_manager.create = AsyncMock(side_effect=[node["uuid"] for node in sample_nodes])

        with patch("sibyl_core.graph.batch.EntityManager", return_value=entity_manager):
            result = await batch_create_nodes(mock_client, org_id, sample_nodes, return_ids=False)

        assert result == []


# =============================================================================
# batch_create_relationships Tests
# =============================================================================
class TestBatchCreateRelationships:
    """Tests for batch_create_relationships function."""

    @pytest.mark.asyncio
    async def test_creates_relationships_with_unwind(
        self, mock_client: MagicMock, org_id: str
    ) -> None:
        """Creates multiple relationships through RelationshipManager."""
        rels = [
            {"from_uuid": "id1", "to_uuid": "id2"},
            {"from_uuid": "id1", "to_uuid": "id3"},
        ]
        relationship_manager = MagicMock()
        relationship_manager.create = AsyncMock(side_effect=["rel-1", "rel-2"])

        with patch("sibyl_core.graph.batch.RelationshipManager", return_value=relationship_manager):
            result = await batch_create_relationships(mock_client, org_id, rels)

        assert result == 2
        assert relationship_manager.create.await_count == 2

    @pytest.mark.asyncio
    async def test_empty_list_returns_zero(self, mock_client: MagicMock, org_id: str) -> None:
        """Empty input returns 0 without query."""
        result = await batch_create_relationships(mock_client, org_id, [])
        assert result == 0

    @pytest.mark.asyncio
    async def test_validates_required_from_uuid(self, mock_client: MagicMock, org_id: str) -> None:
        """Raises ValueError if relationship missing from_uuid."""
        rels = [{"to_uuid": "id2"}]

        with pytest.raises(ValueError, match="missing 'from_uuid'"):
            await batch_create_relationships(mock_client, org_id, rels)

    @pytest.mark.asyncio
    async def test_validates_required_to_uuid(self, mock_client: MagicMock, org_id: str) -> None:
        """Raises ValueError if relationship missing to_uuid."""
        rels = [{"from_uuid": "id1"}]

        with pytest.raises(ValueError, match="missing 'to_uuid'"):
            await batch_create_relationships(mock_client, org_id, rels)

    @pytest.mark.asyncio
    async def test_uses_custom_rel_type(self, mock_client: MagicMock, org_id: str) -> None:
        """Uses specified relationship type."""
        rels = [{"from_uuid": "id1", "to_uuid": "id2"}]
        relationship_manager = MagicMock()
        relationship_manager.create = AsyncMock(return_value="rel-1")

        with patch("sibyl_core.graph.batch.RelationshipManager", return_value=relationship_manager):
            await batch_create_relationships(mock_client, org_id, rels, rel_type="BELONGS_TO")

        relationship = relationship_manager.create.await_args.args[0]
        assert relationship.relationship_type == RelationshipType.BELONGS_TO

    @pytest.mark.asyncio
    async def test_includes_properties(self, mock_client: MagicMock, org_id: str) -> None:
        """Includes properties on relationships."""
        rels = [
            {
                "from_uuid": "id1",
                "to_uuid": "id2",
                "properties": {"weight": 1.0, "created_at": "2024-01-01"},
            }
        ]
        relationship_manager = MagicMock()
        relationship_manager.create = AsyncMock(return_value="rel-1")

        with patch("sibyl_core.graph.batch.RelationshipManager", return_value=relationship_manager):
            await batch_create_relationships(mock_client, org_id, rels)

        relationship = relationship_manager.create.await_args.args[0]
        assert relationship.weight == 1.0
        assert relationship.metadata["created_at"] == "2024-01-01"


# =============================================================================
# batch_update_nodes Tests
# =============================================================================
class TestBatchUpdateNodes:
    """Tests for batch_update_nodes function."""

    @pytest.mark.asyncio
    async def test_updates_nodes_with_unwind(self, mock_client: MagicMock, org_id: str) -> None:
        """Updates multiple nodes through EntityManager."""
        updates = [
            {"uuid": "id1", "properties": {"status": "done"}},
            {"uuid": "id2", "properties": {"status": "doing"}},
        ]
        entity_manager = MagicMock()
        entity_manager.update = AsyncMock(side_effect=[object(), object()])

        with patch("sibyl_core.graph.batch.EntityManager", return_value=entity_manager):
            result = await batch_update_nodes(mock_client, org_id, updates)

        assert result == 2
        assert entity_manager.update.await_count == 2

    @pytest.mark.asyncio
    async def test_empty_list_returns_zero(self, mock_client: MagicMock, org_id: str) -> None:
        """Empty input returns 0 without query."""
        result = await batch_update_nodes(mock_client, org_id, [])
        assert result == 0

    @pytest.mark.asyncio
    async def test_validates_required_uuid(self, mock_client: MagicMock, org_id: str) -> None:
        """Raises ValueError if update missing uuid."""
        updates = [{"properties": {"status": "done"}}]

        with pytest.raises(ValueError, match="missing 'uuid'"):
            await batch_update_nodes(mock_client, org_id, updates)

    @pytest.mark.asyncio
    async def test_validates_required_properties(self, mock_client: MagicMock, org_id: str) -> None:
        """Raises ValueError if update missing properties."""
        updates = [{"uuid": "id1"}]

        with pytest.raises(ValueError, match="missing 'properties'"):
            await batch_update_nodes(mock_client, org_id, updates)

    @pytest.mark.asyncio
    async def test_uses_label_filter(self, mock_client: MagicMock, org_id: str) -> None:
        """Uses label filter when specified."""
        updates = [{"uuid": "id1", "properties": {"status": "done"}}]
        entity_manager = MagicMock()
        entity_manager.get = AsyncMock(
            return_value=Entity(id="id1", name="Task", entity_type=EntityType.TASK)
        )
        entity_manager.update = AsyncMock(return_value=object())

        with patch("sibyl_core.graph.batch.EntityManager", return_value=entity_manager):
            await batch_update_nodes(mock_client, org_id, updates, label="Task")

        entity_manager.get.assert_awaited_once_with("id1")
        entity_manager.update.assert_awaited_once_with("id1", {"status": "done"})


# =============================================================================
# batch_delete_nodes Tests
# =============================================================================
class TestBatchDeleteNodes:
    """Tests for batch_delete_nodes function."""

    @pytest.mark.asyncio
    async def test_deletes_nodes_with_unwind(self, mock_client: MagicMock, org_id: str) -> None:
        """Deletes multiple nodes through EntityManager."""
        uuids = ["id1", "id2", "id3"]
        entity_manager = MagicMock()
        entity_manager.delete = AsyncMock(return_value=True)

        with patch("sibyl_core.graph.batch.EntityManager", return_value=entity_manager):
            result = await batch_delete_nodes(mock_client, org_id, uuids)

        assert result == 3
        assert entity_manager.delete.await_count == 3

    @pytest.mark.asyncio
    async def test_empty_list_returns_zero(self, mock_client: MagicMock, org_id: str) -> None:
        """Empty input returns 0 without query."""
        result = await batch_delete_nodes(mock_client, org_id, [])
        assert result == 0

    @pytest.mark.asyncio
    async def test_uses_detach_by_default(self, mock_client: MagicMock, org_id: str) -> None:
        """Deletes still work with default detach semantics."""
        entity_manager = MagicMock()
        entity_manager.delete = AsyncMock(return_value=True)

        with patch("sibyl_core.graph.batch.EntityManager", return_value=entity_manager):
            await batch_delete_nodes(mock_client, org_id, ["id1"])

        entity_manager.delete.assert_awaited_once_with("id1")

    @pytest.mark.asyncio
    async def test_no_detach_when_disabled(self, mock_client: MagicMock, org_id: str) -> None:
        """detach=False remains a compatible no-op flag."""
        entity_manager = MagicMock()
        entity_manager.delete = AsyncMock(return_value=True)

        with patch("sibyl_core.graph.batch.EntityManager", return_value=entity_manager):
            await batch_delete_nodes(mock_client, org_id, ["id1"], detach=False)

        entity_manager.delete.assert_awaited_once_with("id1")

    @pytest.mark.asyncio
    async def test_uses_label_filter(self, mock_client: MagicMock, org_id: str) -> None:
        """Uses label filter when specified."""
        entity_manager = MagicMock()
        entity_manager.get = AsyncMock(
            return_value=Entity(id="id1", name="Task", entity_type=EntityType.TASK)
        )
        entity_manager.delete = AsyncMock(return_value=True)

        with patch("sibyl_core.graph.batch.EntityManager", return_value=entity_manager):
            await batch_delete_nodes(mock_client, org_id, ["id1"], label="Task")

        entity_manager.get.assert_awaited_once_with("id1")
        entity_manager.delete.assert_awaited_once_with("id1")


# =============================================================================
# Serialization Tests
# =============================================================================
class TestSerialization:
    """Tests for internal serialization helpers."""

    def test_serialize_value_none(self) -> None:
        """None passes through unchanged."""
        assert _serialize_value(None) is None

    def test_serialize_value_datetime(self) -> None:
        """Datetime serialized to ISO format."""
        dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        result = _serialize_value(dt)
        assert result == "2024-01-15T10:30:00+00:00"

    def test_serialize_value_dict(self) -> None:
        """Dict serialized to JSON string."""
        data = {"key": "value", "nested": {"inner": 42}}
        result = _serialize_value(data)
        assert isinstance(result, str)
        assert json.loads(result) == data

    def test_serialize_value_list_of_primitives(self) -> None:
        """List of primitives passes through unchanged."""
        data = [1, 2, 3, "four"]
        result = _serialize_value(data)
        assert result == data

    def test_serialize_value_list_of_dicts(self) -> None:
        """List of dicts serialized to JSON string."""
        data = [{"a": 1}, {"b": 2}]
        result = _serialize_value(data)
        assert isinstance(result, str)
        assert json.loads(result) == data

    def test_serialize_value_enum(self) -> None:
        """Enum serialized to its value."""

        class Status(Enum):
            ACTIVE = "active"
            DONE = "done"

        result = _serialize_value(Status.ACTIVE)
        assert result == "active"

    def test_serialize_value_primitive(self) -> None:
        """Primitives pass through unchanged."""
        assert _serialize_value("string") == "string"
        assert _serialize_value(42) == 42
        assert _serialize_value(3.14) == 3.14
        assert _serialize_value(True) is True

    def test_serialize_node_adds_group_id(self) -> None:
        """Serialized node includes group_id."""
        node = {"uuid": "test-id", "name": "Test"}
        result = _serialize_node(node, "org-123")

        assert result["group_id"] == "org-123"
        assert result["uuid"] == "test-id"
        assert result["name"] == "Test"

    def test_serialize_node_adds_created_at(self) -> None:
        """Serialized node includes created_at timestamp."""
        node = {"uuid": "test-id", "name": "Test"}
        result = _serialize_node(node, "org-123")

        assert "created_at" in result
        # Should be ISO format string
        datetime.fromisoformat(result["created_at"])

    def test_serialize_properties_handles_complex_values(self) -> None:
        """serialize_properties handles all value types."""
        props = {
            "string": "value",
            "number": 42,
            "datetime": datetime(2024, 1, 1, tzinfo=UTC),
            "dict": {"nested": True},
        }
        result = _serialize_properties(props)

        assert result["string"] == "value"
        assert result["number"] == 42
        assert result["datetime"] == "2024-01-01T00:00:00+00:00"
        assert json.loads(result["dict"]) == {"nested": True}


# =============================================================================
# Error Handling Tests
# =============================================================================
class TestErrorHandling:
    """Tests for error handling in batch operations."""

    @pytest.mark.asyncio
    async def test_create_nodes_propagates_errors(
        self, mock_client: MagicMock, org_id: str, sample_nodes: list[dict]
    ) -> None:
        """Errors from EntityManager propagate."""
        entity_manager = MagicMock()
        entity_manager.create = AsyncMock(side_effect=Exception("Database error"))

        with (
            patch("sibyl_core.graph.batch.EntityManager", return_value=entity_manager),
            pytest.raises(Exception, match="Database error"),
        ):
            await batch_create_nodes(mock_client, org_id, sample_nodes)

    @pytest.mark.asyncio
    async def test_create_relationships_propagates_errors(
        self, mock_client: MagicMock, org_id: str
    ) -> None:
        """Errors from RelationshipManager propagate."""
        rels = [{"from_uuid": "id1", "to_uuid": "id2"}]
        relationship_manager = MagicMock()
        relationship_manager.create = AsyncMock(side_effect=Exception("Database error"))

        with (
            patch("sibyl_core.graph.batch.RelationshipManager", return_value=relationship_manager),
            pytest.raises(Exception, match="Database error"),
        ):
            await batch_create_relationships(mock_client, org_id, rels)

    @pytest.mark.asyncio
    async def test_update_nodes_propagates_errors(
        self, mock_client: MagicMock, org_id: str
    ) -> None:
        """Errors from EntityManager propagate."""
        updates = [{"uuid": "id1", "properties": {"status": "done"}}]
        entity_manager = MagicMock()
        entity_manager.update = AsyncMock(side_effect=Exception("Database error"))

        with (
            patch("sibyl_core.graph.batch.EntityManager", return_value=entity_manager),
            pytest.raises(Exception, match="Database error"),
        ):
            await batch_update_nodes(mock_client, org_id, updates)

    @pytest.mark.asyncio
    async def test_delete_nodes_propagates_errors(
        self, mock_client: MagicMock, org_id: str
    ) -> None:
        """Errors from EntityManager propagate."""
        entity_manager = MagicMock()
        entity_manager.delete = AsyncMock(side_effect=Exception("Database error"))

        with (
            patch("sibyl_core.graph.batch.EntityManager", return_value=entity_manager),
            pytest.raises(Exception, match="Database error"),
        ):
            await batch_delete_nodes(mock_client, org_id, ["id1"])
