from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from sibyl.api.routes import graph as graph_routes
from sibyl.api.schemas import SubgraphRequest
from sibyl_core.models.entities import EntityType, RelationshipType


def _org() -> SimpleNamespace:
    return SimpleNamespace(id=UUID("00000000-0000-0000-0000-000000000111"))


class TestGraphRoutes:
    @pytest.mark.asyncio
    async def test_debug_graph_uses_legacy_graph_query_adapter(self) -> None:
        adapter = SimpleNamespace(
            list_entities=AsyncMock(
                return_value=[
                    SimpleNamespace(id="task-1"),
                    SimpleNamespace(id="project-1"),
                ]
            ),
            list_relationships=AsyncMock(
                return_value=[
                    SimpleNamespace(source_id="task-1", target_id="project-1"),
                    SimpleNamespace(source_id="task-1", target_id="missing"),
                ]
            ),
        )

        with patch(
            "sibyl.api.routes.graph.get_legacy_graph_query_adapter",
            AsyncMock(return_value=adapter),
        ):
            result = await graph_routes.debug_graph(org=_org())

        assert result["node_count"] == 2
        assert result["edge_count"] == 2
        assert result["matching_edges"] == 1
        adapter.list_entities.assert_awaited_once_with(limit=500, include_archived=True)
        adapter.list_relationships.assert_awaited_once_with(limit=1000)

    @pytest.mark.asyncio
    async def test_get_all_nodes_uses_legacy_graph_query_adapter(self) -> None:
        adapter = SimpleNamespace(
            list_entities=AsyncMock(
                return_value=[
                    SimpleNamespace(
                        id="task-1",
                        entity_type=EntityType.TASK,
                        name="Task One",
                        description="Center node",
                    )
                ]
            ),
            get_connection_counts=AsyncMock(return_value={"task-1": 3}),
        )

        with patch(
            "sibyl.api.routes.graph.get_legacy_graph_query_adapter",
            AsyncMock(return_value=adapter),
        ):
            nodes = await graph_routes.get_all_nodes(
                org=_org(),
                types=[EntityType.TASK],
                limit=25,
                offset=5,
            )

        assert len(nodes) == 1
        assert nodes[0].id == "task-1"
        assert nodes[0].metadata["connections"] == 3
        adapter.list_entities.assert_awaited_once_with(
            entity_types=[EntityType.TASK],
            limit=25,
            offset=5,
            include_archived=True,
        )
        adapter.get_connection_counts.assert_awaited_once_with(["task-1"])

    @pytest.mark.asyncio
    async def test_get_all_edges_uses_legacy_graph_query_adapter(self) -> None:
        adapter = SimpleNamespace(
            list_relationships=AsyncMock(
                return_value=[
                    SimpleNamespace(
                        id="rel-1",
                        source_id="task-1",
                        target_id="project-1",
                        relationship_type=RelationshipType.BELONGS_TO,
                    )
                ]
            )
        )

        with patch(
            "sibyl.api.routes.graph.get_legacy_graph_query_adapter",
            AsyncMock(return_value=adapter),
        ):
            edges = await graph_routes.get_all_edges(
                org=_org(),
                relationship_types=[RelationshipType.BELONGS_TO],
                limit=25,
                offset=5,
            )

        assert len(edges) == 1
        assert edges[0].source == "task-1"
        assert edges[0].target == "project-1"
        adapter.list_relationships.assert_awaited_once_with(
            relationship_types=[RelationshipType.BELONGS_TO],
            limit=25,
            offset=5,
        )

    @pytest.mark.asyncio
    async def test_get_subgraph_uses_legacy_graph_query_adapter(self) -> None:
        center = SimpleNamespace(
            id="task-1",
            entity_type=EntityType.TASK,
            name="Task One",
            description="Center node",
        )
        related = SimpleNamespace(
            id="project-1",
            entity_type=EntityType.PROJECT,
            name="Project One",
            description="Related node",
        )
        relationship = SimpleNamespace(
            id="rel-1",
            source_id="task-1",
            target_id="project-1",
            relationship_type=RelationshipType.BELONGS_TO,
        )
        entities = {"task-1": center, "project-1": related}
        adapter = SimpleNamespace(
            get_entity=AsyncMock(side_effect=lambda entity_id: entities.get(entity_id)),
            get_related_entities=AsyncMock(return_value=[(related, relationship)]),
        )

        with patch(
            "sibyl.api.routes.graph.get_legacy_graph_query_adapter",
            AsyncMock(return_value=adapter),
        ):
            result = await graph_routes.get_subgraph(
                SubgraphRequest(entity_id="task-1", depth=1, max_nodes=10),
                org=_org(),
            )

        assert result.node_count == 2
        assert result.edge_count == 1
        assert {node.id for node in result.nodes} == {"task-1", "project-1"}
        assert adapter.get_related_entities.await_count == 2
        assert adapter.get_related_entities.await_args_list[0].kwargs == {
            "entity_id": "task-1",
            "relationship_types": None,
            "max_depth": 1,
            "limit": 50,
        }
        assert adapter.get_related_entities.await_args_list[1].kwargs == {
            "entity_id": "project-1",
            "relationship_types": None,
            "max_depth": 1,
            "limit": 50,
        }

    @pytest.mark.asyncio
    async def test_get_clusters_uses_legacy_graph_query_adapter(self) -> None:
        adapter = SimpleNamespace(
            get_clusters_for_visualization=AsyncMock(
                return_value=[
                    SimpleNamespace(
                        id="cluster-1",
                        member_count=3,
                        dominant_type="task",
                        type_distribution={"task": 3},
                        level=0,
                    )
                ]
            )
        )

        with patch(
            "sibyl.api.routes.graph.get_legacy_graph_query_adapter",
            AsyncMock(return_value=adapter),
        ):
            result = await graph_routes.get_clusters(org=_org(), refresh=True)

        assert result["total_nodes"] == 3
        assert result["total_clusters"] == 1
        adapter.get_clusters_for_visualization.assert_awaited_once_with(force_refresh=True)

    @pytest.mark.asyncio
    async def test_get_full_graph_uses_legacy_graph_query_adapter(self) -> None:
        adapter = SimpleNamespace(
            list_entities=AsyncMock(
                return_value=[
                    SimpleNamespace(
                        id="task-1",
                        entity_type=EntityType.TASK,
                        name="Task One",
                    ),
                    SimpleNamespace(
                        id="project-1",
                        entity_type=EntityType.PROJECT,
                        name="Project One",
                    ),
                ]
            ),
            list_relationships_for_entities=AsyncMock(
                return_value=[
                    SimpleNamespace(
                        id="rel-1",
                        source_id="task-1",
                        target_id="project-1",
                        relationship_type=RelationshipType.BELONGS_TO,
                    )
                ]
            ),
        )

        with patch(
            "sibyl.api.routes.graph.get_legacy_graph_query_adapter",
            AsyncMock(return_value=adapter),
        ):
            result = await graph_routes.get_full_graph(
                org=_org(),
                types=[EntityType.TASK, EntityType.PROJECT],
                max_nodes=50,
                max_edges=75,
            )

        assert result.node_count == 2
        assert result.edge_count == 1
        adapter.list_entities.assert_awaited_once_with(
            entity_types=[EntityType.TASK, EntityType.PROJECT],
            limit=50,
            include_archived=True,
        )
        adapter.list_relationships_for_entities.assert_awaited_once()
        assert adapter.list_relationships_for_entities.await_args.args[0] == {"task-1", "project-1"}
        assert adapter.list_relationships_for_entities.await_args.kwargs == {"limit": 75}

    @pytest.mark.asyncio
    async def test_get_hierarchical_graph_data_uses_legacy_graph_query_adapter(self) -> None:
        adapter = SimpleNamespace(
            get_hierarchical_graph=AsyncMock(
                return_value=SimpleNamespace(
                    nodes=[{"id": "task-1", "type": "task", "name": "Task One"}],
                    edges=[{"source": "task-1", "target": "task-2", "type": "RELATED_TO"}],
                    clusters=[{"id": "cluster-1"}],
                    cluster_edges=[],
                    total_nodes=0,
                    total_edges=0,
                    displayed_nodes=1,
                    displayed_edges=1,
                )
            )
        )

        with patch(
            "sibyl.api.routes.graph.get_legacy_graph_query_adapter",
            AsyncMock(return_value=adapter),
        ):
            result = await graph_routes.get_hierarchical_graph_data(
                org=_org(),
                projects=["proj-1"],
                types=[EntityType.TASK],
                max_nodes=200,
                max_edges=300,
            )

        assert result["total_nodes"] == 1
        assert result["total_edges"] == 1
        assert result["nodes"][0]["label"] == "Task One"
        assert result["nodes"][0]["color"] == graph_routes.get_entity_color(EntityType.TASK)
        adapter.get_hierarchical_graph.assert_awaited_once_with(
            project_ids=["proj-1"],
            entity_types=["task"],
            max_nodes=200,
            max_edges=300,
        )
