"""Tests for entity route filtering."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import UUID

import pytest

from sibyl.api.routes import entities as entities_routes
from sibyl.api.routes.entities import SortField, SortOrder, list_entities
from sibyl_core.models.entities import EntityType


def _entity(
    entity_id: str,
    *,
    project_id: str | None,
    name: str,
    archived: bool = False,
    status: str | None = None,
) -> SimpleNamespace:
    metadata = {"project_id": project_id} if project_id else {}
    if archived:
        metadata["archived"] = True
    if status is not None:
        metadata["status"] = status
    return SimpleNamespace(
        id=entity_id,
        entity_type=EntityType.TASK,
        name=name,
        description="",
        content="",
        metadata=metadata,
        languages=[],
        tags=[],
    )


class TestListEntitiesRoute:
    @pytest.mark.asyncio
    async def test_single_project_entities_push_project_filter_into_graph_query(self) -> None:
        org = SimpleNamespace(id=UUID("00000000-0000-0000-0000-000000000111"))
        manager = MagicMock()
        manager._surreal_entity_node_ops.return_value = object()
        manager.list_by_type = AsyncMock(
            side_effect=[
                [
                    _entity("ent-match", project_id="proj-1", name="Match"),
                    _entity("ent-other", project_id="proj-2", name="Other"),
                ],
                [],
            ]
        )
        manager.list_all = AsyncMock()
        runtime = SimpleNamespace(entity_manager=manager)

        with patch(
            "sibyl.api.routes.entities.get_entity_graph_runtime",
            AsyncMock(return_value=runtime),
        ):
            response = await list_entities(
                org=org,
                entity_type=EntityType.TASK,
                language=None,
                category=None,
                search=None,
                project_ids=["proj-1"],
                page=1,
                page_size=50,
                sort_by=SortField.UPDATED_AT,
                sort_order=SortOrder.DESC,
            )

        assert manager.list_by_type.await_args_list == [
            call(
                EntityType.TASK,
                limit=1000,
                offset=0,
                include_archived=True,
                project_id="proj-1",
            ),
        ]
        manager.list_all.assert_not_awaited()
        assert [entity.id for entity in response.entities] == ["ent-match"]
        assert response.total == 1
        assert response.has_more is False

    @pytest.mark.asyncio
    async def test_mixed_project_and_unassigned_entities_keep_python_filtering(self) -> None:
        org = SimpleNamespace(id=UUID("00000000-0000-0000-0000-000000000111"))
        manager = MagicMock()
        manager.list_by_type = AsyncMock(
            side_effect=[
                [
                    _entity("ent-match", project_id="proj-1", name="Match"),
                    _entity("ent-other", project_id="proj-2", name="Other"),
                    _entity("ent-unassigned", project_id=None, name="Unassigned"),
                ],
                [],
            ]
        )
        manager.list_all = AsyncMock()
        runtime = SimpleNamespace(entity_manager=manager)

        with patch(
            "sibyl.api.routes.entities.get_entity_graph_runtime",
            AsyncMock(return_value=runtime),
        ):
            response = await list_entities(
                org=org,
                entity_type=EntityType.TASK,
                language=None,
                category=None,
                search=None,
                project_ids=["proj-1", "__unassigned__"],
                page=1,
                page_size=50,
                sort_by=SortField.UPDATED_AT,
                sort_order=SortOrder.DESC,
            )

        assert manager.list_by_type.await_args_list == [
            call(
                EntityType.TASK,
                limit=1000,
                offset=0,
                include_archived=True,
            ),
        ]
        manager.list_all.assert_not_awaited()
        assert [entity.id for entity in response.entities] == [
            "ent-match",
            "ent-unassigned",
        ]
        assert response.total == 2
        assert response.has_more is False

    @pytest.mark.asyncio
    async def test_typed_entity_queries_page_past_first_batch(self) -> None:
        org = SimpleNamespace(id=UUID("00000000-0000-0000-0000-000000000111"))
        manager = MagicMock()
        manager.list_by_type = AsyncMock(
            side_effect=[
                [
                    _entity(
                        "ent-archived-1",
                        project_id="proj-1",
                        name="Archived 1",
                        archived=True,
                    ),
                    _entity(
                        "ent-archived-2",
                        project_id="proj-2",
                        name="Archived 2",
                        status="archived",
                    ),
                ],
                [
                    _entity("ent-1", project_id="proj-1", name="One"),
                    _entity("ent-2", project_id="proj-2", name="Two"),
                ],
                [
                    _entity("ent-3", project_id="proj-3", name="Three"),
                ],
                [],
            ]
        )
        manager.list_all = AsyncMock()
        runtime = SimpleNamespace(entity_manager=manager)

        with (
            patch.object(entities_routes, "LIST_BY_TYPE_PAGE_SIZE", 2),
            patch(
                "sibyl.api.routes.entities.get_entity_graph_runtime",
                AsyncMock(return_value=runtime),
            ),
        ):
            response = await list_entities(
                org=org,
                entity_type=EntityType.TASK,
                language=None,
                category=None,
                search=None,
                project_ids=None,
                page=1,
                page_size=50,
                sort_by=SortField.UPDATED_AT,
                sort_order=SortOrder.DESC,
            )

        assert manager.list_by_type.await_args_list == [
            call(EntityType.TASK, limit=2, offset=0, include_archived=True),
            call(EntityType.TASK, limit=2, offset=2, include_archived=True),
            call(EntityType.TASK, limit=2, offset=4, include_archived=True),
        ]
        manager.list_all.assert_not_awaited()
        assert [entity.id for entity in response.entities] == ["ent-1", "ent-2", "ent-3"]
        assert response.total == 3
        assert response.has_more is False

    @pytest.mark.asyncio
    async def test_default_surreal_entity_query_stops_after_page_has_more_probe(self) -> None:
        org = SimpleNamespace(id=UUID("00000000-0000-0000-0000-000000000111"))
        manager = MagicMock()
        manager._surreal_entity_node_ops.return_value = object()
        manager.list_by_type = AsyncMock(
            return_value=[
                _entity("ent-1", project_id="proj-1", name="One"),
                _entity("ent-2", project_id="proj-1", name="Two"),
            ]
        )
        manager.list_all = AsyncMock()
        runtime = SimpleNamespace(entity_manager=manager)

        with (
            patch.object(entities_routes, "LIST_BY_TYPE_PAGE_SIZE", 2),
            patch(
                "sibyl.api.routes.entities.get_entity_graph_runtime",
                AsyncMock(return_value=runtime),
            ),
        ):
            response = await list_entities(
                org=org,
                entity_type=EntityType.TASK,
                language=None,
                category=None,
                search=None,
                project_ids=["proj-1"],
                page=1,
                page_size=1,
                sort_by=SortField.UPDATED_AT,
                sort_order=SortOrder.DESC,
            )

        manager.list_by_type.assert_awaited_once_with(
            EntityType.TASK,
            limit=2,
            offset=0,
            include_archived=True,
            project_id="proj-1",
        )
        manager.list_all.assert_not_awaited()
        assert [entity.id for entity in response.entities] == ["ent-1"]
        assert response.total == 2
        assert response.has_more is True

    @pytest.mark.asyncio
    async def test_default_legacy_entity_query_keeps_exhaustive_sorting(self) -> None:
        org = SimpleNamespace(id=UUID("00000000-0000-0000-0000-000000000111"))
        manager = MagicMock()
        manager._surreal_entity_node_ops.return_value = None
        older = _entity("older-returned-first", project_id=None, name="Older")
        newer = _entity("newer-returned-second", project_id=None, name="Newer")
        older.updated_at = datetime(2024, 1, 1, tzinfo=UTC)
        newer.updated_at = datetime(2025, 1, 1, tzinfo=UTC)
        manager.list_by_type = AsyncMock(
            side_effect=[
                [older],
                [newer],
                [],
            ]
        )
        manager.list_all = AsyncMock()
        runtime = SimpleNamespace(entity_manager=manager)

        with (
            patch.object(entities_routes, "LIST_BY_TYPE_PAGE_SIZE", 1),
            patch(
                "sibyl.api.routes.entities.get_entity_graph_runtime",
                AsyncMock(return_value=runtime),
            ),
        ):
            response = await list_entities(
                org=org,
                entity_type=EntityType.TASK,
                language=None,
                category=None,
                search=None,
                project_ids=None,
                page=1,
                page_size=1,
                sort_by=SortField.UPDATED_AT,
                sort_order=SortOrder.DESC,
            )

        assert [entity.id for entity in response.entities] == ["newer-returned-second"]
        assert response.total == 2
        assert response.has_more is True

    @pytest.mark.asyncio
    async def test_untyped_project_filters_skip_archived_only_pages(self) -> None:
        org = SimpleNamespace(id=UUID("00000000-0000-0000-0000-000000000111"))
        manager = MagicMock()
        archived_page = [
            _entity("ent-archived-1", project_id="proj-1", name="Archived 1", archived=True),
            _entity("ent-archived-2", project_id="proj-1", name="Archived 2", archived=True),
        ]
        live_page = [
            _entity("ent-match", project_id="proj-1", name="Match"),
            _entity("ent-unassigned", project_id=None, name="Unassigned"),
        ]
        manager.list_by_type = AsyncMock()
        manager.list_all = AsyncMock(side_effect=[archived_page, live_page, []])
        runtime = SimpleNamespace(entity_manager=manager)

        with (
            patch.object(entities_routes, "LIST_ALL_PAGE_SIZE", 2),
            patch(
                "sibyl.api.routes.entities.get_entity_graph_runtime",
                AsyncMock(return_value=runtime),
            ),
        ):
            response = await list_entities(
                org=org,
                entity_type=None,
                language=None,
                category=None,
                search=None,
                project_ids=["proj-1", "__unassigned__"],
                page=1,
                page_size=50,
                sort_by=SortField.UPDATED_AT,
                sort_order=SortOrder.DESC,
            )

        manager.list_by_type.assert_not_awaited()
        assert manager.list_all.await_args_list == [
            call(limit=2, offset=0, include_archived=True),
            call(limit=2, offset=2, include_archived=True),
            call(limit=2, offset=4, include_archived=True),
        ]
        assert [entity.id for entity in response.entities] == ["ent-match", "ent-unassigned"]
        assert response.total == 2
        assert response.has_more is False
