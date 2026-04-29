"""Tests for active graph runtime services."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import sibyl_core.services as services
from sibyl_core.services import (
    ActiveGraphRuntime,
    execute_graph_query,
    get_graph_client,
    get_graph_runtime,
)


@pytest.mark.asyncio
async def test_get_graph_runtime_binds_active_store_managers() -> None:
    client = AsyncMock()
    entity_manager = object()
    relationship_manager = object()

    with (
        patch("sibyl_core.graph.client.get_graph_client", AsyncMock(return_value=client)),
        patch(
            "sibyl_core.graph.entities.EntityManager", return_value=entity_manager
        ) as entity_ctor,
        patch(
            "sibyl_core.graph.relationships.RelationshipManager",
            return_value=relationship_manager,
        ) as relationship_ctor,
    ):
        runtime = await get_graph_runtime("org-123")

    assert isinstance(runtime, ActiveGraphRuntime)
    assert runtime.client is client
    assert runtime.entity_manager is entity_manager
    assert runtime.relationship_manager is relationship_manager
    entity_ctor.assert_called_once_with(client, group_id="org-123")
    relationship_ctor.assert_called_once_with(client, group_id="org-123")


def test_services_package_exports_only_neutral_graph_helpers() -> None:
    assert services.ActiveGraphRuntime is ActiveGraphRuntime
    assert services.get_graph_client is get_graph_client
    assert services.get_graph_runtime is get_graph_runtime
    assert services.execute_graph_query is execute_graph_query
    assert "LegacyGraphRuntime" not in services.__all__
    assert "get_legacy_graph_client" not in services.__all__
    assert "get_legacy_graph_runtime" not in services.__all__
    assert "execute_legacy_graph_query" not in services.__all__


@pytest.mark.asyncio
async def test_execute_graph_query_normalizes_driver_result() -> None:
    client = MagicMock()
    driver = AsyncMock()
    driver.execute_query = AsyncMock(return_value=({"row": "ignored"},))
    client.client = SimpleNamespace(driver=MagicMock())
    client.client.driver.clone.return_value = driver
    client.normalize_result.return_value = [{"row": "value"}]

    with patch(
        "sibyl_core.services.graph_runtime.get_graph_client", AsyncMock(return_value=client)
    ):
        result = await execute_graph_query("org-123", "RETURN $value", value="x")

    assert result == [{"row": "value"}]
    client.client.driver.clone.assert_called_once_with("org-123")
    driver.execute_query.assert_awaited_once_with("RETURN $value", value="x")
    client.normalize_result.assert_called_once()


@pytest.mark.asyncio
async def test_execute_graph_query_rejects_cypher_on_surreal_driver() -> None:
    client = MagicMock()
    driver = AsyncMock()
    driver.execute_query = AsyncMock()
    client.client = SimpleNamespace(driver=MagicMock())
    client.client.driver.clone.return_value = driver

    with (
        patch("sibyl_core.services.graph_runtime.get_graph_client", AsyncMock(return_value=client)),
        patch("sibyl_core.services.graph_runtime._is_surreal_driver", return_value=True),
        pytest.raises(ValueError, match="SurrealQL"),
    ):
        await execute_graph_query("org-123", "MATCH (n) RETURN n")

    driver.execute_query.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_graph_query_allows_surrealql_on_surreal_driver() -> None:
    client = MagicMock()
    driver = AsyncMock()
    driver.execute_query = AsyncMock(return_value=({"row": "ignored"},))
    client.client = SimpleNamespace(driver=MagicMock())
    client.client.driver.clone.return_value = driver
    client.normalize_result.return_value = [{"row": "value"}]

    with (
        patch("sibyl_core.services.graph_runtime.get_graph_client", AsyncMock(return_value=client)),
        patch("sibyl_core.services.graph_runtime._is_surreal_driver", return_value=True),
    ):
        result = await execute_graph_query("org-123", "SELECT * FROM entity")

    assert result == [{"row": "value"}]
    driver.execute_query.assert_awaited_once_with("SELECT * FROM entity")


@pytest.mark.asyncio
async def test_execute_graph_query_ignores_cypher_tokens_in_strings_and_comments() -> None:
    client = MagicMock()
    driver = AsyncMock()
    driver.execute_query = AsyncMock(return_value=({"row": "ignored"},))
    client.client = SimpleNamespace(driver=MagicMock())
    client.client.driver.clone.return_value = driver
    client.normalize_result.return_value = [{"row": "value"}]
    query = """
        SELECT 'MATCH (n)', "CALL db.indexes", `UNWIND`
        FROM entity
        WHERE url = 'https://example.com//MATCH'
        /* UNWIND ignored */
        -- MATCH ignored
    """

    with (
        patch("sibyl_core.services.graph_runtime.get_graph_client", AsyncMock(return_value=client)),
        patch("sibyl_core.services.graph_runtime._is_surreal_driver", return_value=True),
    ):
        result = await execute_graph_query("org-123", query)

    assert result == [{"row": "value"}]
    driver.execute_query.assert_awaited_once_with(query)


@pytest.mark.asyncio
async def test_execute_graph_query_rejects_token_after_comment_quote() -> None:
    client = MagicMock()
    driver = AsyncMock()
    driver.execute_query = AsyncMock()
    client.client = SimpleNamespace(driver=MagicMock())
    client.client.driver.clone.return_value = driver
    query = """
        -- stray ' quote in comment
        MATCH (n) RETURN n
    """

    with (
        patch("sibyl_core.services.graph_runtime.get_graph_client", AsyncMock(return_value=client)),
        patch("sibyl_core.services.graph_runtime._is_surreal_driver", return_value=True),
        pytest.raises(ValueError, match="SurrealQL"),
    ):
        await execute_graph_query("org-123", query)

    driver.execute_query.assert_not_awaited()
