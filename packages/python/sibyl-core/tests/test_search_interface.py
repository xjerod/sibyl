"""Tests for sibyl_core.graph.search_interface."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from graphiti_core.search.search_filters import ComparisonOperator, DateFilter, SearchFilters

from sibyl_core.backends.surreal import SurrealDriver
from sibyl_core.graph.search_interface import FalkorDBSearchInterface, SurrealSearchInterface


class FakeSurrealSearchDriver:
    def __init__(self, records: list[dict[str, Any]]) -> None:
        self.records = records
        self.queries: list[tuple[str, dict[str, Any]]] = []

    def build_fulltext_query(self, query: str) -> str:
        return query.strip()

    async def execute_query(self, cypher_query_: str, **params: Any) -> list[dict[str, Any]]:
        self.queries.append((cypher_query_, params))
        return deepcopy(self.records)


class TestFalkorDBSearchInterface:
    """Ensure fallback Graphiti searches do not mutate shared driver state."""

    @pytest.mark.asyncio
    async def test_node_similarity_search_uses_driver_copy(self) -> None:
        interface = FalkorDBSearchInterface()
        original_search_interface = object()
        driver = SimpleNamespace(search_interface=original_search_interface, marker="shared")

        async def fake_node_similarity_search(*args, **kwargs):  # type: ignore[no-untyped-def]
            passed_driver = args[0]
            assert passed_driver is not driver
            assert passed_driver.marker == "shared"
            assert passed_driver.search_interface is None
            assert driver.search_interface is original_search_interface
            return ["node-result"]

        with patch(
            "graphiti_core.search.search_utils.node_similarity_search",
            side_effect=fake_node_similarity_search,
        ):
            result = await interface.node_similarity_search(
                driver,
                [0.1, 0.2],
                None,
                ["org-123"],
                10,
                0.7,
            )

        assert result == ["node-result"]
        assert driver.search_interface is original_search_interface

    @pytest.mark.asyncio
    async def test_fallback_searches_do_not_race_on_shared_driver(self) -> None:
        interface = FalkorDBSearchInterface()
        original_search_interface = object()
        driver = SimpleNamespace(search_interface=original_search_interface, marker="shared")

        async def fake_node_similarity_search(*args, **kwargs):  # type: ignore[no-untyped-def]
            passed_driver = args[0]
            assert passed_driver is not driver
            assert passed_driver.search_interface is None
            assert driver.search_interface is original_search_interface
            await asyncio.sleep(0)
            assert driver.search_interface is original_search_interface
            return ["node-result"]

        async def fake_episode_fulltext_search(*args, **kwargs):  # type: ignore[no-untyped-def]
            passed_driver = args[0]
            assert passed_driver is not driver
            assert passed_driver.search_interface is None
            assert driver.search_interface is original_search_interface
            await asyncio.sleep(0)
            assert driver.search_interface is original_search_interface
            return ["episode-result"]

        with (
            patch(
                "graphiti_core.search.search_utils.node_similarity_search",
                side_effect=fake_node_similarity_search,
            ),
            patch(
                "graphiti_core.search.search_utils.episode_fulltext_search",
                side_effect=fake_episode_fulltext_search,
            ),
        ):
            node_result, episode_result = await asyncio.gather(
                interface.node_similarity_search(
                    driver,
                    [0.1, 0.2],
                    None,
                    ["org-123"],
                    10,
                    0.7,
                ),
                interface.episode_fulltext_search(
                    driver,
                    "graph search",
                    None,
                    ["org-123"],
                    10,
                ),
            )

        assert node_result == ["node-result"]
        assert episode_result == ["episode-result"]
        assert driver.search_interface is original_search_interface


class TestSurrealSearchInterface:
    @pytest.mark.asyncio
    async def test_node_fulltext_search_uses_surrealql(self) -> None:
        now = datetime.now(UTC)
        driver = FakeSurrealSearchDriver(
            [
                {
                    "uuid": "node-1",
                    "name": "Graph Memory",
                    "name_embedding": None,
                    "group_id": "org-1",
                    "labels": ["Entity", "Pattern"],
                    "created_at": now,
                    "summary": "Surreal graph search",
                    "attributes": {},
                }
            ]
        )

        result = await SurrealSearchInterface().node_fulltext_search(
            driver,
            "graph memory",
            SearchFilters(node_labels=["Pattern"]),
            ["org-1"],
            5,
        )

        query, params = driver.queries[0]
        assert "CALL " not in query
        assert "MATCH " not in query
        assert "FROM entity" in query
        assert "name @0@ $query" in query
        assert params["group_ids"] == ["org-1"]
        assert params["node_label"] == "Pattern"
        assert result[0].uuid == "node-1"

    @pytest.mark.asyncio
    async def test_edge_similarity_search_uses_surreal_vector_query(self) -> None:
        now = datetime.now(UTC)
        driver = FakeSurrealSearchDriver(
            [
                {
                    "uuid": "edge-1",
                    "name": "RELATES_TO",
                    "fact": "Sibyl uses SurrealDB",
                    "fact_embedding": [0.1, 0.2],
                    "group_id": "org-1",
                    "episodes": [],
                    "attributes": {},
                    "created_at": now,
                    "expired_at": None,
                    "valid_at": now,
                    "invalid_at": None,
                    "source_node_uuid": "src-1",
                    "target_node_uuid": "tgt-1",
                }
            ]
        )

        result = await SurrealSearchInterface().edge_similarity_search(
            driver,
            [0.1, 0.2],
            "src-1",
            "tgt-1",
            SearchFilters(
                edge_uuids=["edge-1"],
                valid_at=[
                    [
                        DateFilter(
                            date=now,
                            comparison_operator=ComparisonOperator.greater_than_equal,
                        )
                    ]
                ],
            ),
            ["org-1"],
            5,
            0.6,
        )

        query, params = driver.queries[0]
        assert "CALL " not in query
        assert "MATCH " not in query
        assert "FROM relates_to" in query
        assert "fact_embedding <|20, 40|> $search_vector" in query
        assert params["source_node_uuid"] == "src-1"
        assert params["target_node_uuid"] == "tgt-1"
        assert params["edge_uuids"] == ["edge-1"]
        assert params["valid_at_0_0"] == now
        assert "valid_at >= $valid_at_0_0" in query
        assert result[0].uuid == "edge-1"

    def test_surreal_driver_installs_native_search_interface(self) -> None:
        assert isinstance(SurrealDriver("memory://").search_interface, SurrealSearchInterface)
