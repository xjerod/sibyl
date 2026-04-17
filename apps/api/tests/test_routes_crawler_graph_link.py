from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from sibyl.api.routes import crawler as crawler_routes
from sibyl.api.schemas import LinkGraphRequest


@pytest.mark.asyncio
async def test_process_graph_linking_maps_graph_connection_errors_to_503() -> None:
    with (
        patch(
            "sibyl.crawler.graph_integration.create_graph_integration_service",
            AsyncMock(side_effect=RuntimeError("offline")),
        ) as create_integration,
        pytest.raises(HTTPException) as exc_info,
    ):
        await crawler_routes._process_graph_linking(
            source_id=None,
            request=LinkGraphRequest(),
            organization_id=str(uuid4()),
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Graph service unavailable"
    create_integration.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_graph_linking_maps_configuration_errors_to_503() -> None:
    with (
        patch(
            "sibyl.crawler.graph_integration.create_graph_integration_service",
            AsyncMock(side_effect=ValueError("missing api key")),
        ) as create_integration,
        pytest.raises(HTTPException) as exc_info,
    ):
        await crawler_routes._process_graph_linking(
            source_id=None,
            request=LinkGraphRequest(create_new_entities=True),
            organization_id=str(uuid4()),
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Entity extraction not configured"
    create_integration.assert_awaited_once()
