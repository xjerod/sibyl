"""Tests for crawler status routes."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from sibyl.api.routes.crawler import get_link_graph_status


class TestLinkGraphStatusRoute:
    """Tests for /sources/link-graph/status."""

    @pytest.mark.asyncio
    async def test_keeps_same_name_sources_distinct(self) -> None:
        """Status groups by stable source ID instead of collapsing on name."""
        org_id = UUID("00000000-0000-0000-0000-000000000111")
        org = SimpleNamespace(id=org_id)

        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar=MagicMock(return_value=12)),
                MagicMock(scalar=MagicMock(return_value=5)),
                MagicMock(
                    all=MagicMock(
                        return_value=[
                            SimpleNamespace(
                                source_id=UUID("00000000-0000-0000-0000-000000000aaa"),
                                name="Docs",
                                pending=4,
                            ),
                            SimpleNamespace(
                                source_id=UUID("00000000-0000-0000-0000-000000000bbb"),
                                name="Docs",
                                pending=3,
                            ),
                        ]
                    )
                ),
            ]
        )

        @asynccontextmanager
        async def mock_session():
            yield session

        with patch("sibyl.api.routes.crawler.get_session", mock_session):
            response = await get_link_graph_status(org=org)

        rendered_queries = [str(call.args[0]) for call in session.execute.await_args_list]

        assert response.total_chunks == 12
        assert response.chunks_with_entities == 5
        assert response.chunks_pending == 7
        assert [source.model_dump() for source in response.sources] == [
            {
                "source_id": "00000000-0000-0000-0000-000000000aaa",
                "name": "Docs",
                "pending": 4,
            },
            {
                "source_id": "00000000-0000-0000-0000-000000000bbb",
                "name": "Docs",
                "pending": 3,
            },
        ]
        assert all("organization_id" in query for query in rendered_queries)
