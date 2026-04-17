"""Tests for admin routes."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from sibyl.api.routes.admin import DebugQueryRequest, debug_query, health, stats


@pytest.mark.asyncio
async def test_health_passes_org_context_to_core_health() -> None:
    org = SimpleNamespace(id=UUID("00000000-0000-0000-0000-000000000111"))
    mock_get_health = AsyncMock(
        return_value={
            "status": "healthy",
            "server_name": "sibyl",
            "uptime_seconds": 42,
            "graph_connected": True,
            "entity_counts": {"task": 3},
            "errors": [],
        }
    )

    with patch("sibyl_core.tools.core.get_health", mock_get_health):
        response = await health(org=org)

    assert response.status == "healthy"
    assert response.entity_counts == {"task": 3}
    mock_get_health.assert_awaited_once_with(organization_id=str(org.id))


@pytest.mark.asyncio
async def test_stats_uses_legacy_graph_stats_payload() -> None:
    org = SimpleNamespace(id=UUID("00000000-0000-0000-0000-000000000111"))
    mock_get_stats = AsyncMock(
        return_value={
            "entity_counts": {"task": 4, "pattern": 1},
            "total_entities": 5,
        }
    )

    with patch("sibyl.api.routes.admin.get_legacy_graph_stats_payload", mock_get_stats):
        response = await stats(org=org)

    assert response.total_entities == 5
    assert response.entity_counts == {"task": 4, "pattern": 1}
    mock_get_stats.assert_awaited_once_with(str(org.id))


@pytest.mark.asyncio
async def test_debug_query_uses_legacy_debug_runner() -> None:
    org = SimpleNamespace(id=UUID("00000000-0000-0000-0000-000000000111"))
    request = DebugQueryRequest(cypher="MATCH (n) RETURN n LIMIT 1", params={"limit": 1})
    mock_execute = AsyncMock(return_value=[{"value": ("node",)}])

    with patch("sibyl.api.routes.admin.execute_legacy_debug_query", mock_execute):
        response = await debug_query(request=request, org=org)

    assert response.rows == [{"value": ("node",)}]
    assert response.row_count == 1
    mock_execute.assert_awaited_once_with(
        "MATCH (n) RETURN n LIMIT 1",
        group_id=str(org.id),
        limit=1,
    )
